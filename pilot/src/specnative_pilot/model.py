from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlsplit

from smolagents import OpenAIServerModel as _OpenAIServerModel

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
        model_id = (self.model_id or "").casefold()
        base_url = (getattr(self, "client_kwargs", {}) or {}).get("base_url") or ""
        try:
            hostname = (urlsplit(base_url).hostname or "").casefold()
        except ValueError:
            hostname = ""
        return hostname == "api.groq.com" and model_id.startswith("openai/gpt-oss-")

    def _is_missing_tool_call_error(self, error: BaseException) -> bool:
        return (
            getattr(error, "status_code", None) == 400
            and _TOOL_CHOICE_ERROR.casefold() in str(error).casefold()
        )

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
            if (
                not self._is_groq_gpt_oss()
                or not tools_to_call_from
                or kwargs.get("tool_choice", "required") != "required"
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
    return OpenAIServerModel(
        model_id=credentials.model,
        api_base=credentials.api_base,
        api_key=credentials.api_key,
        **model_options,
    )
