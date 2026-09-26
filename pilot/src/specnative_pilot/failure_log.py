from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote_plus, urlencode, urlsplit, urlunsplit


MAX_LOG_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5
_BEARER_RE = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_TOKEN_RE = re.compile(r"\b(?:gsk_|sk-proj-|sk-)[A-Za-z0-9_-]{8,}\b")
_SECRET_FIELD_RE = re.compile(
    r"(?i)([\"']?\b(?:api[_-]?key|access[_-]?token|token|secret)[\"']?\s*[=:]\s*[\"']?)[^\s,;&}\"']+"
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def log_directory_candidates(
    *,
    platform: str | None = None,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Path]:
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else home
    environ = os.environ if environ is None else environ
    if platform == "darwin":
        user_logs = home / "Library" / "Logs" / "asn"
    else:
        state_home = Path(environ.get("XDG_STATE_HOME") or home / ".local" / "state").expanduser()
        if not state_home.is_absolute():
            state_home = home / ".local" / "state"
        user_logs = state_home / "asn" / "logs"
    candidates = [Path("/var/log/asn"), user_logs, Path("/tmp/asn")]
    return list(dict.fromkeys(candidates))


def _safe_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.netloc:
            return "[URL OCULTA]"
        hostname = parts.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        try:
            port = f":{parts.port}" if parts.port is not None else ""
        except ValueError:
            port = ""
        query_pairs: list[tuple[str, str]] = []
        for part in parts.query.split("&"):
            if not part:
                continue
            key, separator, _ = part.partition("=")
            display_key = unquote_plus(key) if separator else "[PARAMETRO_OCULTO]"
            query_pairs.append((display_key, "[OCULTO]"))
        query = urlencode(query_pairs)
        return urlunsplit((parts.scheme, hostname + port, parts.path, query, ""))
    except ValueError:
        return "[URL OCULTA]"


def _sanitize_text(value: str, api_key: str | None = None) -> str:
    value = _SECRET_FIELD_RE.sub(r"\1[OCULTO]", value)
    value = _BEARER_RE.sub(r"\1[CREDENCIAL OCULTA]", value)
    value = _TOKEN_RE.sub("[CREDENCIAL OCULTA]", value)
    if api_key:
        value = value.replace(api_key, "[CREDENCIAL OCULTA]")
    return _URL_RE.sub(lambda match: _safe_url(match.group(0).rstrip(".,;:)")), value)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(record.msg, ensure_ascii=False, separators=(",", ":"))


class _PrivateRotatingHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:
            stream.close()
            raise
        return stream

    def handleError(self, record: logging.LogRecord) -> None:
        error = sys.exc_info()[1]
        if error is not None:
            raise error
        raise OSError("No se pudo escribir el log de fallas ASN")


class FailureLog:
    def __init__(
        self,
        directories: list[Path] | None = None,
        *,
        max_bytes: int = MAX_LOG_BYTES,
        backup_count: int = BACKUP_COUNT,
    ) -> None:
        self.directories = directories or log_directory_candidates()
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._handler: _PrivateRotatingHandler | None = None
        self._directory_index = 0
        self._lock = threading.Lock()

    @property
    def path(self) -> Path | None:
        if self._handler is None:
            return None
        return Path(self._handler.baseFilename)

    def _open_handler(self, directory: Path) -> _PrivateRotatingHandler:
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)
        handler = _PrivateRotatingHandler(
            directory / "asn-failures.jsonl",
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
            delay=False,
        )
        handler.setFormatter(_JsonFormatter())
        return handler

    def _record(self, event: dict[str, object]) -> None:
        record = logging.LogRecord(
            name="specnative_pilot.failures",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg=event,
            args=(),
            exc_info=None,
        )
        with self._lock:
            while self._directory_index < len(self.directories):
                if self._handler is None:
                    try:
                        self._handler = self._open_handler(self.directories[self._directory_index])
                    except OSError:
                        self._directory_index += 1
                        continue
                try:
                    self._handler.emit(record)
                    return
                except OSError:
                    self._handler.close()
                    self._handler = None
                    self._directory_index += 1
        try:
            print(
                "ASN: no se pudo guardar el log de fallas en ninguna ubicación; "
                "revise los permisos de /var/log/asn, los logs del usuario y /tmp/asn.",
                file=sys.stderr,
            )
        except OSError:
            pass

    def record_failure(
        self,
        operation: str,
        error: BaseException,
        *,
        model: str | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
        include_traceback: bool = False,
    ) -> None:
        message = _sanitize_text(str(error)[:2000], api_key)
        event: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "operation": operation,
            "model": model or None,
            "endpoint": _safe_url(endpoint) if endpoint else None,
            "error_type": type(error).__name__,
            "message": message,
        }
        if include_traceback and error.__traceback__ is not None:
            rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            event["traceback"] = _sanitize_text(rendered[-12000:], api_key)
        self._record(event)


_default_failure_log = FailureLog()


def record_failure(
    operation: str,
    error: BaseException,
    *,
    model: str | None = None,
    endpoint: str | None = None,
    api_key: str | None = None,
    include_traceback: bool = False,
) -> None:
    _default_failure_log.record_failure(
        operation,
        error,
        model=model,
        endpoint=endpoint,
        api_key=api_key,
        include_traceback=include_traceback,
    )
