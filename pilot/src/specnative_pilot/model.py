from __future__ import annotations

from copy import deepcopy
import json
from uuid import uuid4
from urllib.parse import urlsplit

from smolagents import OpenAIServerModel as _OpenAIServerModel
from smolagents.models import ChatMessageToolCall, ChatMessageToolCallFunction, MessageRole

from .config import Config, effective_reasoning_effort
from .model_eval import ModelEvalLog, TracingOpenAIClient
from .secrets import SecretResolutionError, resolve_credentials


_TOOL_CHOICE_ERROR = "Tool choice is required, but model did not call a tool"
_RETRY_INSTRUCTION = (
    "La respuesta anterior no llamó ninguna herramienta y el proveedor la rechazó. "
    "Reintenta este mismo turno llamando exactamente una herramienta disponible. "
    "Si corresponde responder directamente, usa la herramienta final_answer."
)


class ToolCallRetryExhausted(RuntimeError):
    """Marks the final provider error after ASN's one targeted retry."""

    def __init__(self, error: BaseException, attempts: int) -> None:
        super().__init__(str(error))
        self.asn_tool_call_attempts = max(1, attempts)


def _append_retry_instruction(messages):
    retry_messages = deepcopy(messages)
    if retry_messages:
        last = retry_messages[-1]
        role = last.get("role") if isinstance(last, dict) else last.role
        if getattr(role, "value", role) == "user":
            content = last.get("content") if isinstance(last, dict) else last.content
            if isinstance(content, list):
                content.append({"type": "text", "text": _RETRY_INSTRUCTION})
            elif isinstance(content, str) and content:
                content = [
                    {"type": "text", "text": content},
                    {"type": "text", "text": _RETRY_INSTRUCTION},
                ]
            else:
                content = [{"type": "text", "text": _RETRY_INSTRUCTION}]
            if isinstance(last, dict):
                last["content"] = content
            else:
                last.content = content
            return retry_messages

    # Tool responses are normalized to the user role by smolagents. A text
    # string in a new adjacent user message trips get_clean_message_list's
    # same-role merge assertion; structured text blocks are mergeable.
    retry_messages.append({
        "role": "user",
        "content": [{"type": "text", "text": _RETRY_INSTRUCTION}],
    })
    return retry_messages


def _is_groq_gpt_oss(model_id: str | None, api_base: str | None) -> bool:
    model_name = (model_id or "").casefold()
    try:
        hostname = (urlsplit(api_base or "").hostname or "").casefold()
    except ValueError:
        hostname = ""
    return hostname == "api.groq.com" and model_name.startswith("openai/gpt-oss-")


def tool_call_attempts(error: BaseException) -> int:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        attempts = getattr(current, "asn_tool_call_attempts", None)
        if isinstance(attempts, int):
            return attempts
        current = current.__cause__ or current.__context__
    return 1


class OpenAIServerModel(_OpenAIServerModel):
    """OpenAI-compatible model with one narrowly scoped Groq tool-call retry."""

    def __init__(self, *args, eval_log: ModelEvalLog | None = None, **kwargs) -> None:
        self.eval_log = eval_log or ModelEvalLog()
        super().__init__(*args, **kwargs)

    def create_client(self):
        client = super().create_client()
        endpoint = (getattr(self, "client_kwargs", {}) or {}).get("base_url")
        return TracingOpenAIClient(client, self.eval_log, self.model_id or "", endpoint)

    @property
    def eval_log_path(self):
        return self.eval_log.path

    def _is_groq_gpt_oss(self) -> bool:
        base_url = (getattr(self, "client_kwargs", {}) or {}).get("base_url")
        return _is_groq_gpt_oss(self.model_id, base_url)

    def _is_missing_tool_call_error(self, error: BaseException) -> bool:
        return (
            getattr(error, "status_code", None) == 400
            and _TOOL_CHOICE_ERROR.casefold() in str(error).casefold()
        )

    def parse_tool_calls(self, message):
        if not self._is_groq_gpt_oss():
            return super().parse_tool_calls(message)

        # Groq GPT-OSS may answer directly after its last tool call, or encode
        # a final answer as a `json` pseudo-tool. smolagents expects the
        # `final_answer` tool schema, so normalize these two final-only shapes.
        if message.tool_calls:
            for call in message.tool_calls:
                function = call.function
                arguments = function.arguments
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except (TypeError, ValueError):
                        continue
                if (
                    function.name == "json"
                    and isinstance(arguments, dict)
                    and set(arguments) == {"answer"}
                    and isinstance(arguments["answer"], str)
                ):
                    function.name = "final_answer"
                    function.arguments = arguments
            return message

        try:
            return super().parse_tool_calls(message)
        except (AssertionError, ValueError):
            if not isinstance(message.content, str) or not message.content.strip():
                raise
            message.role = MessageRole.ASSISTANT
            message.tool_calls = [
                ChatMessageToolCall(
                    id=f"asn-{uuid4().hex}",
                    type="function",
                    function=ChatMessageToolCallFunction(
                        name="final_answer",
                        arguments={"answer": message.content.strip()},
                    ),
                )
            ]
            return message

    def generate(
        self,
        messages,
        stop_sequences=None,
        response_format=None,
        tools_to_call_from=None,
        **kwargs,
    ):
        eval_log = getattr(self, "eval_log", None)
        calls_before = eval_log.request_count if eval_log is not None else 0
        try:
            return super().generate(
                messages,
                stop_sequences=stop_sequences,
                response_format=response_format,
                tools_to_call_from=tools_to_call_from,
                **kwargs,
            )
        except Exception as error:
            effective_tool_choice = kwargs.get(
                "tool_choice",
                (getattr(self, "kwargs", {}) or {}).get("tool_choice", "required"),
            )
            if (
                not self._is_groq_gpt_oss()
                or not tools_to_call_from
                or effective_tool_choice != "required"
                or not self._is_missing_tool_call_error(error)
            ):
                raise

        retry_messages = _append_retry_instruction(messages)
        try:
            return super().generate(
                retry_messages,
                stop_sequences=stop_sequences,
                response_format=response_format,
                tools_to_call_from=tools_to_call_from,
                **kwargs,
            )
        except Exception as retry_error:
            attempts = eval_log.request_count - calls_before if eval_log is not None else 1
            raise ToolCallRetryExhausted(retry_error, attempts) from retry_error


def build_model(config: Config) -> OpenAIServerModel:
    try:
        credentials = resolve_credentials(config)
    except SecretResolutionError as error:
        raise RuntimeError(str(error)) from error
    if not credentials.model:
        raise RuntimeError(
            "Falta el modelo ASN. Configura SPECNATIVE_AGENT_MODEL, [agent].model o ejecuta `asn --auth`."
        )
    if not credentials.api_key:
        raise RuntimeError(
            f"No existe una API key en el backend configurado ni en la variable {config.api_key_env}; "
            "configúrala en el entorno o ejecuta `asn --auth`."
        )
    reasoning_effort = effective_reasoning_effort(
        config,
        model=credentials.model,
        api_base=credentials.api_base,
    )
    model_options = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    if _is_groq_gpt_oss(credentials.model, credentials.api_base):
        # GPT-OSS can otherwise be forced to call a tool even when it has
        # completed the task. On Groq this may surface as an invalid `json`
        # pseudo-tool call; auto still allows requested MCP tool calls and
        # lets the agent finish with a normal assistant response.
        model_options["tool_choice"] = "auto"
    return OpenAIServerModel(
        model_id=credentials.model,
        api_base=credentials.api_base,
        api_key=credentials.api_key,
        **model_options,
    )
