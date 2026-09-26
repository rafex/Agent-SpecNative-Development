from __future__ import annotations

from urllib.parse import urlsplit

from smolagents import OpenAIServerModel as _OpenAIServerModel

from .config import Config, effective_reasoning_effort
from .secrets import SecretResolutionError, resolve_credentials


_TOOL_CHOICE_ERROR = "Tool choice is required, but model did not call a tool"
_RETRY_INSTRUCTION = (
    "La respuesta anterior no llamó ninguna herramienta y el proveedor la rechazó. "
    "Reintenta este mismo turno llamando exactamente una herramienta disponible. "
    "Si corresponde responder directamente, usa la herramienta final_answer."
)


class ToolCallRetryExhausted(RuntimeError):
    """Marks the final provider error after ASN's one targeted retry."""

    asn_tool_call_attempts = 2


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

        retry_messages = [
            *messages,
            {"role": "user", "content": _RETRY_INSTRUCTION},
        ]
        try:
            return super().generate(
                retry_messages,
                stop_sequences=stop_sequences,
                response_format=response_format,
                tools_to_call_from=tools_to_call_from,
                **kwargs,
            )
        except Exception as retry_error:
            raise ToolCallRetryExhausted(str(retry_error)) from retry_error


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
