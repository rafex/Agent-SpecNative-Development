from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import json
import time
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
_EMPTY_OUTPUT_RETRY_INSTRUCTION = (
    "La respuesta anterior llegó vacía. Continúa este mismo turno y produce una respuesta "
    "utilizable. Si tienes herramientas disponibles, usa una apropiada o llama final_answer; "
    "si no tienes herramientas, responde directamente. No repitas el razonamiento."
)
_EMPTY_OUTPUT_MAX_ATTEMPTS = 12
_INITIAL_MAX_COMPLETION_TOKENS = 1024
_MAX_COMPLETION_TOKENS = 65536
_RETRY_BACKOFF_INITIAL_SECONDS = 0.25
_RETRY_BACKOFF_MAX_SECONDS = 2.0


class ToolCallRetryExhausted(RuntimeError):
    """Marks the final provider error after ASN's one targeted retry."""

    def __init__(self, error: BaseException, attempts: int) -> None:
        super().__init__(str(error))
        self.asn_tool_call_attempts = max(1, attempts)


class EmptyModelOutputError(RuntimeError):
    """Successful completion had neither user-facing content nor a tool call."""

    def __init__(self, attempts: int, finish_reason: str | None = None) -> None:
        detail = (
            "El proveedor devolvió respuestas exitosas sin contenido ni llamada a herramienta "
            f"en {attempts} intentos."
        )
        if finish_reason:
            detail += f" finish_reason={finish_reason}."
        super().__init__(detail)
        self.asn_tool_call_attempts = max(1, attempts)


def find_empty_model_output_error(error: BaseException) -> EmptyModelOutputError | None:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, EmptyModelOutputError):
            return current
        current = current.__cause__ or current.__context__
    return None


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


def _append_empty_output_retry_instruction(messages):
    retry_messages = deepcopy(messages)
    if retry_messages:
        last = retry_messages[-1]
        role = last.get("role") if isinstance(last, dict) else last.role
        if getattr(role, "value", role) == "user":
            content = last.get("content") if isinstance(last, dict) else last.content
            if isinstance(content, list):
                content.append({"type": "text", "text": _EMPTY_OUTPUT_RETRY_INSTRUCTION})
            elif isinstance(content, str) and content:
                content = [
                    {"type": "text", "text": content},
                    {"type": "text", "text": _EMPTY_OUTPUT_RETRY_INSTRUCTION},
                ]
            else:
                content = [{"type": "text", "text": _EMPTY_OUTPUT_RETRY_INSTRUCTION}]
            if isinstance(last, dict):
                last["content"] = content
            else:
                last.content = content
            return retry_messages
    retry_messages.append({
        "role": "user",
        "content": [{"type": "text", "text": _EMPTY_OUTPUT_RETRY_INSTRUCTION}],
    })
    return retry_messages


def _is_empty_completion(message: Any) -> bool:
    return not getattr(message, "tool_calls", None) and not str(
        getattr(message, "content", "") or ""
    ).strip()


def _finish_reason(message: Any) -> str | None:
    try:
        value = message.raw.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return None
    return str(value) if value is not None else None


def _unsupported_parameter(error: BaseException, parameter: str) -> bool:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).casefold()
        if parameter.casefold() in message and any(
            marker in message for marker in ("unsupported", "unrecognized", "unknown", "not allowed", "invalid")
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


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
    """OpenAI-compatible model with bounded empty-output and Groq tool-call retries."""

    def __init__(self, *args, eval_log: ModelEvalLog | None = None, call_history=None, **kwargs) -> None:
        self.eval_log = eval_log or ModelEvalLog()
        self.call_history = call_history
        super().__init__(*args, **kwargs)

    def create_client(self):
        client = super().create_client()
        endpoint = (getattr(self, "client_kwargs", {}) or {}).get("base_url")
        return TracingOpenAIClient(client, self.eval_log, self.model_id or "", endpoint, self.call_history)

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

    @contextmanager
    def _retry_with_low_reasoning(self):
        model_kwargs = getattr(self, "kwargs", {})
        had_reasoning_effort = "reasoning_effort" in model_kwargs
        previous_reasoning_effort = model_kwargs.get("reasoning_effort")
        model_kwargs["reasoning_effort"] = "low"
        try:
            yield
        finally:
            if had_reasoning_effort:
                model_kwargs["reasoning_effort"] = previous_reasoning_effort
            else:
                model_kwargs.pop("reasoning_effort", None)

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
        is_groq_with_tools = self._is_groq_gpt_oss() and bool(tools_to_call_from)
        max_completion_tokens = kwargs.get(
            "max_completion_tokens", _INITIAL_MAX_COMPLETION_TOKENS
        )
        if is_groq_with_tools:
            kwargs.setdefault("max_completion_tokens", max_completion_tokens)
        attempts = 1
        try:
            response = super().generate(
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
                response = super().generate(
                    retry_messages,
                    stop_sequences=stop_sequences,
                    response_format=response_format,
                    tools_to_call_from=tools_to_call_from,
                    **kwargs,
                )
                attempts += 1
            except Exception as retry_error:
                attempts = eval_log.request_count - calls_before if eval_log is not None else 2
                raise ToolCallRetryExhausted(retry_error, attempts) from retry_error

        if _is_empty_completion(response):
            retry_messages = _append_empty_output_retry_instruction(messages)
            while _is_empty_completion(response) and attempts < _EMPTY_OUTPUT_MAX_ATTEMPTS:
                delay = min(
                    _RETRY_BACKOFF_INITIAL_SECONDS * 2 ** (attempts - 1),
                    _RETRY_BACKOFF_MAX_SECONDS,
                )
                time.sleep(delay)
                if _finish_reason(response) == "length":
                    max_completion_tokens = min(
                        max_completion_tokens * 2,
                        _MAX_COMPLETION_TOKENS,
                    )
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("max_tokens", None)
                retry_kwargs["max_completion_tokens"] = max_completion_tokens
                with self._retry_with_low_reasoning():
                    try:
                        response = super().generate(
                            retry_messages,
                            stop_sequences=stop_sequences,
                            response_format=response_format,
                            tools_to_call_from=tools_to_call_from,
                            **retry_kwargs,
                        )
                        attempts += 1
                    except Exception as error:
                        attempts += 1
                        if not _unsupported_parameter(error, "max_completion_tokens") or attempts >= _EMPTY_OUTPUT_MAX_ATTEMPTS:
                            try:
                                error.asn_tool_call_attempts = attempts
                            except Exception:
                                pass
                            raise
                        fallback_kwargs = dict(retry_kwargs)
                        fallback_kwargs.pop("max_completion_tokens", None)
                        fallback_kwargs["max_tokens"] = max_completion_tokens
                        response = super().generate(
                            retry_messages,
                            stop_sequences=stop_sequences,
                            response_format=response_format,
                            tools_to_call_from=tools_to_call_from,
                            **fallback_kwargs,
                        )
                        attempts += 1
            if _is_empty_completion(response):
                raise EmptyModelOutputError(attempts, _finish_reason(response))
        return response


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
    from .history import HistoryStore

    call_history = HistoryStore(
        config.repo / ".specnative" / "agent" / "memory.sqlite3" if config.history else None
    )
    return OpenAIServerModel(
        model_id=credentials.model,
        api_base=credentials.api_base,
        api_key=credentials.api_key,
        call_history=call_history,
        **model_options,
    )
