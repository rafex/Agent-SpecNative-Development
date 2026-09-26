from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import uuid4


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _jsonable(model_dump(mode="json"))
        except TypeError:
            return _jsonable(model_dump())
    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        return _jsonable(to_dict())
    return str(value)


def _safe_endpoint(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parts = urlsplit(value)
        hostname = parts.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        port = f":{parts.port}" if parts.port is not None else ""
        query = urlencode(
            [(key.partition("=")[0], "[OCULTO]") for key in parts.query.split("&") if key]
        )
        return urlunsplit((parts.scheme, hostname + port, parts.path, query, ""))
    except ValueError:
        return "[URL OCULTA]"


class ModelEvalLog:
    """Private, temporary JSONL trace of requests sent to the model provider."""

    def __init__(self, directory: Path | None = None) -> None:
        if directory is None:
            directory = Path(tempfile.mkdtemp(prefix="asn-eval-"))
        else:
            directory.mkdir(parents=True, mode=0o700, exist_ok=False)
        os.chmod(directory, 0o700)
        self.directory = directory
        self.path = directory / "model-calls.jsonl"
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        self._lock = threading.Lock()
        self._request_count = 0

    @property
    def request_count(self) -> int:
        with self._lock:
            return self._request_count

    def request_started(self) -> int:
        with self._lock:
            self._request_count += 1
            return self._request_count

    def record(
        self,
        request_id: int,
        *,
        request: dict[str, Any],
        response: Any = None,
        error: BaseException | None = None,
        elapsed_ms: float,
        model: str | None,
        endpoint: str | None,
    ) -> None:
        # These are SDK transport options, never part of the model payload.
        safe_request = {
            key: value
            for key, value in request.items()
            if key.casefold() not in {"headers", "extra_headers", "authorization", "api_key"}
        }
        event: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "model": model,
            "endpoint": _safe_endpoint(endpoint),
            "reasoning_effort": safe_request.get("reasoning_effort"),
            "elapsed_ms": round(max(0.0, elapsed_ms), 3),
            "request": _jsonable(safe_request),
            "response": _jsonable(response),
        }
        if error is not None:
            event["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "status_code": getattr(error, "status_code", None),
                "body": _jsonable(getattr(error, "body", None)),
            }
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                os.chmod(self.path, 0o600)
                handle.write(line)
                handle.flush()


class _TracingCompletions:
    def __init__(self, completions: Any, eval_log: ModelEvalLog, model: str, endpoint: str | None) -> None:
        self._completions = completions
        self._eval_log = eval_log
        self._model = model
        self._endpoint = endpoint

    def create(self, **request: Any) -> Any:
        request_id = self._eval_log.request_started()
        started = time.perf_counter()
        try:
            response = self._completions.create(**request)
        except Exception as error:
            self._eval_log.record(
                request_id,
                request=request,
                response=getattr(error, "body", None),
                error=error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                model=self._model,
                endpoint=self._endpoint,
            )
            raise
        self._eval_log.record(
            request_id,
            request=request,
            response=response,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            model=self._model,
            endpoint=self._endpoint,
        )
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._completions, name)


class _TracingChat:
    def __init__(self, chat: Any, eval_log: ModelEvalLog, model: str, endpoint: str | None) -> None:
        self._chat = chat
        self.completions = _TracingCompletions(chat.completions, eval_log, model, endpoint)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class TracingOpenAIClient:
    """Delegate to an OpenAI client while tracing chat completion calls only."""

    def __init__(self, client: Any, eval_log: ModelEvalLog, model: str, endpoint: str | None) -> None:
        self._client = client
        self.chat = _TracingChat(client.chat, eval_log, model, endpoint)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
