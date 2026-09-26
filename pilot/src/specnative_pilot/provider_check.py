from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable
from urllib.parse import unquote_plus, urlencode, urlsplit, urlunsplit

from .secrets import ResolvedCredentials


class ProviderTestError(RuntimeError):
    """A safe, user-facing error from the provider connectivity check."""


@dataclass(frozen=True)
class ProviderTestResult:
    model: str
    response: str
    status_code: int


@dataclass(frozen=True)
class _ProviderRequest:
    url: str
    body: str
    curl_config: str
    summary: str


_PROBE_TOOL_NAME = "asn_tool_call_probe"
_PROBE_VALUE = "ASN tool calling funciona"


def _chat_completions_url(api_base: str | None) -> str:
    base = (api_base or "https://api.openai.com/v1").strip()
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ProviderTestError("La URL base debe ser una dirección HTTP o HTTPS válida.")
    path = parts.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path = f"{path}/chat/completions"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _display_url(url: str) -> str:
    """Hide URL credentials, query values, and fragments in diagnostic output."""
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = f":{parts.port}" if parts.port is not None else ""
    except ValueError:
        port = ""
    netloc = f"{hostname}{port}"
    query_pairs = []
    for part in parts.query.split("&"):
        if not part:
            continue
        key, separator, _ = part.partition("=")
        display_key = unquote_plus(key) if separator else "[PARAMETRO_OCULTO]"
        query_pairs.append((display_key, "[OCULTO]"))
    query = urlencode(query_pairs)
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def _curl_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n") + '"'


def _redact(value: str, token: str) -> str:
    return value.replace(token, "[REDACTADO]") if token else value


def _mask_token(token: str) -> str:
    if len(token) <= 8:
        return "[OCULTO]"
    return f"{token[:4]}…{token[-4:]}"


def _prepare_request(credentials: ResolvedCredentials, reasoning_effort: str | None = None) -> _ProviderRequest:
    payload = {
        "model": credentials.model,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Llama a {_PROBE_TOOL_NAME} con ok igual a `{_PROBE_VALUE}`. "
                    "Devuelve exclusivamente la llamada a la herramienta."
                ),
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": _PROBE_TOOL_NAME,
                    "description": "Valida que el proveedor puede emitir llamadas a herramientas.",
                    "parameters": {
                        "type": "object",
                        "properties": {"ok": {"type": "string"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": "required",
        "max_completion_tokens": 1024,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    url = _chat_completions_url(credentials.api_base)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    curl_config = "\n".join(
        (
            f"url = {_curl_quote(url)}",
            f"header = {_curl_quote('Authorization: Bearer ' + credentials.api_key)}",
            f"header = {_curl_quote('Content-Type: application/json')}",
        )
    )
    summary = "\n".join(
        (
            "Petición de diagnóstico:",
            f"POST {_display_url(url)}",
            f"Modelo: {credentials.model}",
            f"Authorization: Bearer {_mask_token(credentials.api_key or '')}",
            "Content-Type: application/json",
            "Cuerpo:",
            body,
        )
    )
    return _ProviderRequest(url=url, body=body, curl_config=curl_config, summary=summary)


def check_provider(
    credentials: ResolvedCredentials,
    *,
    reasoning_effort: str | None = None,
    on_request: Callable[[str], None] | None = None,
) -> ProviderTestResult:
    """Send one minimal OpenAI-compatible request with curl without exposing the token."""
    if not credentials.api_key or not credentials.api_key.strip():
        raise ProviderTestError("Falta el token de API; configura credenciales antes de ejecutar `asn --test`.")
    if not credentials.model or not credentials.model.strip():
        raise ProviderTestError("Falta el nombre del modelo; configura credenciales antes de ejecutar `asn --test`.")
    if "\r" in credentials.api_key or "\n" in credentials.api_key:
        raise ProviderTestError("El token contiene caracteres de salto de línea y no se puede validar.")

    request = _prepare_request(credentials, reasoning_effort)
    if on_request is not None:
        on_request(request.summary)
    curl = shutil.which("curl")
    if curl is None:
        raise ProviderTestError("No se encontró `curl`; instálalo y vuelve a ejecutar `asn --test`.")
    # curl reads the Authorization header from stdin config, so the token is
    # absent from argv, process listings, and diagnostic output.
    try:
        result = subprocess.run(
            [
                curl,
                "--silent",
                "--show-error",
                "--connect-timeout",
                "10",
                "--max-time",
                "30",
                "--write-out",
                "\n%{http_code}",
                "--data-binary",
                request.body,
                "--config",
                "-",
            ],
            input=request.curl_config,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        detail = _redact(str(error), credentials.api_key)
        raise ProviderTestError(f"No se pudo ejecutar curl contra el proveedor: {detail}") from error

    output = result.stdout or ""
    response_body, separator, status_text = output.rpartition("\n")
    if not separator or not status_text.isdigit():
        detail = _redact((result.stderr or "curl no devolvió una respuesta HTTP válida.").strip(), credentials.api_key)
        raise ProviderTestError(f"Falló la conexión con el proveedor: {detail}")
    status_code = int(status_text)
    if result.returncode != 0:
        detail = _redact((result.stderr or f"curl terminó con código {result.returncode}.").strip(), credentials.api_key)
        raise ProviderTestError(f"Falló la conexión con el proveedor: {detail}")

    try:
        payload = json.loads(response_body)
    except (TypeError, ValueError):
        payload = None
    if status_code < 200 or status_code >= 300:
        message = ""
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or "")
            elif error:
                message = str(error)
        message = _redact(message, credentials.api_key).strip()
        suffix = f": {message[:400]}" if message else ""
        raise ProviderTestError(f"El proveedor respondió HTTP {status_code}{suffix}")
    try:
        choice = payload["choices"][0]
        message = choice["message"]
    except (TypeError, KeyError, IndexError, AttributeError):
        raise ProviderTestError(
            f"El proveedor respondió HTTP {status_code}, pero el cuerpo no tiene el formato Chat Completions esperado."
        )
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        details: list[str] = []
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None:
            details.append(f"finish_reason={_redact(str(finish_reason), credentials.api_key)}")
        if isinstance(message, dict):
            details.append("campos del mensaje=" + ", ".join(sorted(str(key) for key in message.keys())))
        suffix = f" ({'; '.join(details)})" if details else ""
        raise ProviderTestError(
            f"El proveedor respondió HTTP {status_code}, pero no emitió exactamente una llamada a herramienta{suffix}."
        )
    try:
        function = tool_calls[0]["function"]
        arguments = function["arguments"]
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
    except (TypeError, KeyError, ValueError):
        raise ProviderTestError(
            f"El proveedor respondió HTTP {status_code}, pero la llamada de diagnóstico tiene argumentos inválidos."
        )
    if function.get("name") != _PROBE_TOOL_NAME or not isinstance(arguments, dict) or arguments.get("ok") != _PROBE_VALUE:
        raise ProviderTestError(
            f"El proveedor respondió HTTP {status_code}, pero la llamada de diagnóstico no coincide con la herramienta esperada."
        )
    return ProviderTestResult(
        model=credentials.model,
        response=f"tool call `{_PROBE_TOOL_NAME}` validada",
        status_code=status_code,
    )
