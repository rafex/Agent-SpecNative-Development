from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import struct
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_endpoint(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        port = f":{parts.port}" if parts.port is not None else ""
        return urlunsplit((parts.scheme, host + port, parts.path, "", ""))
    except ValueError:
        return "[URL OCULTA]"


class EmbeddingClient:
    """OpenAI-compatible embedding client with an independent endpoint/key."""

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None, call_history=None) -> None:
        from openai import OpenAI

        self.model = model
        self.base_url = base_url
        self.call_history = call_history
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, text: str) -> list[float]:
        started = time.perf_counter()
        error = None
        result = None
        try:
            result = self.client.embeddings.create(model=self.model, input=text)
            return list(result.data[0].embedding)
        except Exception as caught:
            error = caught
            raise
        finally:
            if self.call_history is not None:
                usage = getattr(result, "usage", None)
                self.call_history.record_call(
                    model=self.model,
                    endpoint=_safe_endpoint(self.base_url),
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    success=error is None,
                    error_type=type(error).__name__ if error else None,
                    request_type="embedding",
                    input_tokens=getattr(usage, "prompt_tokens", None),
                )


class HistoryStore:
    """Per-repository SQLite call history and visible conversation memory."""

    def __init__(self, path: Path | None, embedding_client: EmbeddingClient | None = None) -> None:
        self.path = path
        self.embedding_client = embedding_client
        self.vector_error: str | None = None
        self.vector_enabled = embedding_client is not None
        self._sqlite_vec: Any = None
        self._vector_lock = threading.RLock()
        self._reindex_thread: threading.Thread | None = None
        self._cancel_reindex = threading.Event()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                os.chmod(path.parent, 0o700)
            except OSError:
                pass
            try:
                import sqlite_vec

                self._sqlite_vec = sqlite_vec
            except ImportError:
                self.vector_enabled = False
                self.vector_error = "No se pudo cargar sqlite-vec; se guardará el historial sin búsqueda vectorial."
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS calls (
                        id INTEGER PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        model TEXT,
                        endpoint TEXT,
                        elapsed_ms REAL NOT NULL,
                        success INTEGER NOT NULL,
                        error_type TEXT,
                        status_code INTEGER,
                        finish_reason TEXT,
                        request_type TEXT NOT NULL DEFAULT 'chat',
                        cached_tokens INTEGER,
                        input_tokens INTEGER,
                        output_tokens INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS turns (
                        id INTEGER PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        session_id TEXT,
                        initiative TEXT NOT NULL,
                        user_message TEXT NOT NULL,
                        assistant_message TEXT NOT NULL,
                        source_hash TEXT UNIQUE
                    );
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    """
                )
                columns = {row[1] for row in connection.execute("PRAGMA table_info(calls)")}
                for name, declaration in (
                    ("request_type", "TEXT NOT NULL DEFAULT 'chat'"),
                    ("cached_tokens", "INTEGER"),
                    ("input_tokens", "INTEGER"),
                    ("output_tokens", "INTEGER"),
                ):
                    if name not in columns:
                        connection.execute(f"ALTER TABLE calls ADD COLUMN {name} {declaration}")
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
            self._import_legacy_jsonl()
            if embedding_client is not None and self.vector_enabled:
                self.configure_embeddings(embedding_client)

    @contextmanager
    def _connect(self):
        if self.path is None:
            raise RuntimeError("El historial está deshabilitado.")
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        if self._sqlite_vec is not None:
            try:
                connection.enable_load_extension(True)
                self._sqlite_vec.load(connection)
                connection.enable_load_extension(False)
            except (sqlite3.Error, OSError) as error:
                try:
                    connection.enable_load_extension(False)
                except sqlite3.Error:
                    pass
                self.vector_enabled = False
                self.vector_error = f"No se pudo activar sqlite-vec ({type(error).__name__}); el historial seguirá disponible."
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _import_legacy_jsonl(self) -> None:
        if self.path is None:
            return
        legacy = self.path.parent / "sessions" / "latest.jsonl"
        if not legacy.is_file():
            return
        try:
            lines = legacy.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                record = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(record, dict) and record.get("event") in {"user", "agent"}:
                events.append(record)
        pending: dict[str, Any] | None = None
        with self._connect() as connection:
            imported = connection.execute("SELECT value FROM metadata WHERE key='legacy_jsonl_imported'").fetchone()
            if imported:
                return
            for record in events:
                if record["event"] == "user":
                    pending = record
                elif pending is not None and pending.get("initiative") == record.get("initiative"):
                    user_message = str(pending.get("message", ""))
                    assistant_message = str(record.get("response", ""))
                    digest = hashlib.sha256(
                        (str(pending.get("timestamp", "")) + "\0" + user_message + "\0" + assistant_message).encode()
                    ).hexdigest()
                    connection.execute(
                        "INSERT OR IGNORE INTO turns(timestamp,initiative,user_message,assistant_message,source_hash) VALUES(?,?,?,?,?)",
                        (str(pending.get("timestamp") or record.get("timestamp") or _now()), str(record.get("initiative") or ""), user_message, assistant_message, digest),
                    )
                    pending = None
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES('legacy_jsonl_imported',?)",
                (_now(),),
            )

    def append(self, event: str, **data: Any) -> None:
        """Compatibility method for callers recording visible user/agent events."""
        if event == "user":
            self._pending_user = data
        elif event == "agent":
            pending = getattr(self, "_pending_user", None)
            if pending is not None:
                self.record_turn(
                    str(pending.get("message", "")),
                    str(data.get("response", "")),
                    initiative=str(data.get("initiative", pending.get("initiative", ""))),
                )
                self._pending_user = None

    def record_turn(
        self,
        user_message: str,
        assistant_message: str,
        *,
        initiative: str,
        session_id: str | None = None,
    ) -> None:
        if self.path is None:
            return
        with self._vector_lock:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO turns(timestamp,session_id,initiative,user_message,assistant_message) VALUES(?,?,?,?,?)",
                    (_now(), session_id, initiative, user_message, assistant_message),
                )
                turn_id = int(cursor.lastrowid)
            if self.vector_enabled and self.embedding_client is not None:
                self._start_reindex()

    def record_call(
        self,
        *,
        model: str,
        endpoint: str | None,
        elapsed_ms: float,
        success: bool,
        error_type: str | None = None,
        status_code: int | None = None,
        finish_reason: str | None = None,
        request_type: str = "chat",
        cached_tokens: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        if self.path is None:
            return
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO calls(timestamp,model,endpoint,elapsed_ms,success,error_type,status_code,finish_reason,request_type,cached_tokens,input_tokens,output_tokens) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (_now(), model, endpoint, max(0.0, float(elapsed_ms)), int(success), error_type, status_code, finish_reason, request_type, cached_tokens, input_tokens, output_tokens),
            )

    def _set_vector_error(self, message: str) -> None:
        self.vector_enabled = False
        self.vector_error = message

    def configure_embeddings(self, embedding_client: EmbeddingClient) -> None:
        """Select an embedding profile and schedule a resumable background reindex."""
        self.embedding_client = embedding_client
        if self.path is None or self._sqlite_vec is None:
            self.vector_enabled = False
            return
        self.vector_enabled = True
        self.vector_error = None
        self._start_reindex()

    @staticmethod
    def embedding_profile_fingerprint(model: str, base_url: str | None) -> str:
        raw = f"{base_url or ''}\0{model}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def mark_embedding_profile_tested(self, model: str, base_url: str | None) -> None:
        if self.path is None:
            return
        fingerprint = self.embedding_profile_fingerprint(model, base_url)
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_test_fingerprint',?)", (fingerprint,))

    def embedding_profile_was_tested(self, embedding_client: EmbeddingClient) -> bool:
        if self.path is None:
            return False
        fingerprint = self.embedding_profile_fingerprint(embedding_client.model, embedding_client.base_url)
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key='embedding_test_fingerprint'").fetchone()
        return bool(row and row[0] == fingerprint)

    def _embedding_fingerprint(self) -> str:
        client = self.embedding_client
        if client is None:
            return ""
        return self.embedding_profile_fingerprint(getattr(client, "model", ""), getattr(client, "base_url", None))

    def _table_for_fingerprint(self, fingerprint: str) -> str:
        return "memory_vectors_" + re.sub(r"[^a-f0-9]", "", fingerprint)

    def _start_reindex(self) -> None:
        if self.path is None or self.embedding_client is None or self._sqlite_vec is None:
            return
        with self._vector_lock:
            fingerprint = self._embedding_fingerprint()
            with self._connect() as connection:
                state_key = "vector_state_" + fingerprint
                metadata = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('vector_active_fingerprint',?)", (state_key,)))
                table = self._table_for_fingerprint(fingerprint)
                total = connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
                indexed = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if self._table_exists(connection, table) else 0
                if metadata.get(state_key) == "ready" and total <= indexed:
                    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_active_fingerprint',?)", (fingerprint,))
                    return
                if total == 0 and metadata.get(state_key) == "ready":
                    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_active_fingerprint',?)", (fingerprint,))
                    return
                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?, 'building')", (state_key,))
                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("vector_build_fingerprint_" + fingerprint, fingerprint))
            self.vector_error = "La memoria vectorial se está reconstruyendo en segundo plano."
            if self._reindex_thread is None or not self._reindex_thread.is_alive():
                self._cancel_reindex = threading.Event()
                self._reindex_thread = threading.Thread(target=self._reindex_worker, args=(fingerprint, self._cancel_reindex), name="asn-vector-reindex", daemon=True)
                self._reindex_thread.start()

    def _reindex_worker(self, fingerprint: str, cancel: threading.Event) -> None:
        table = self._table_for_fingerprint(fingerprint)
        state_key = "vector_state_" + fingerprint
        embedding_client = self.embedding_client
        try:
            if self.path is None or embedding_client is None:
                return
            lock_path = self.path.with_suffix(self.path.suffix + ".reindex.lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with lock_path.open("a+b") as lock_file:
                os.chmod(lock_path, 0o600)
                try:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                except ImportError:
                    fcntl = None
                dimension: int | None = None
                while True:
                    if cancel.is_set():
                        return
                    with self._vector_lock:
                        with self._connect() as connection:
                            metadata = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN (?,?)", ("vector_build_dimension_" + fingerprint, state_key)))
                            dimension = int(metadata["vector_build_dimension_" + fingerprint]) if metadata.get("vector_build_dimension_" + fingerprint) else dimension
                            if metadata.get(state_key) == "ready":
                                total = connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
                                indexed = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if self._table_exists(connection, table) else 0
                                if total <= indexed:
                                    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_active_fingerprint',?)", (fingerprint,))
                                    return
                            rows = connection.execute(
                                f"SELECT id,initiative,user_message,assistant_message FROM turns WHERE id NOT IN (SELECT rowid FROM {table}) ORDER BY id LIMIT 32"
                                if self._table_exists(connection, table)
                                else "SELECT id,initiative,user_message,assistant_message FROM turns ORDER BY id LIMIT 32"
                            ).fetchall()
                            if not rows:
                                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_active_fingerprint',?)", (fingerprint,))
                                if dimension is not None:
                                    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_dimension',?)", (str(dimension),))
                                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?, 'ready')", (state_key,))
                                connection.execute("DELETE FROM metadata WHERE key IN (?,?)", ("vector_build_fingerprint_" + fingerprint, "vector_build_dimension_" + fingerprint))
                                self.vector_error = None
                                return
                    for row in rows:
                        vector = embedding_client.embed(f"Usuario: {row['user_message']}\nAgente: {row['assistant_message']}")
                        if cancel.is_set():
                            return
                        if not vector:
                            raise ValueError("embedding vacío")
                        if dimension is not None and len(vector) != dimension:
                            raise ValueError("dimensiones de embedding inconsistentes")
                        dimension = len(vector)
                        with self._vector_lock:
                            if cancel.is_set():
                                return
                            with self._connect() as connection:
                                if not self._table_exists(connection, table):
                                    connection.execute(f"CREATE VIRTUAL TABLE {table} USING vec0(embedding float[{dimension}], +initiative TEXT)")
                                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", ("vector_build_dimension_" + fingerprint, str(dimension)))
                                connection.execute(
                                    f"INSERT OR REPLACE INTO {table}(rowid,embedding,initiative) VALUES(?,?,?)",
                                    (row["id"], self._serialize_vector(vector), row["initiative"]),
                                )
        except Exception as error:
            self._set_vector_error(f"No se pudo reconstruir el índice vectorial ({type(error).__name__}); el historial SQL se conserva.")
            try:
                with self._connect() as connection:
                    connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?, 'failed')", (state_key,))
            except Exception:
                pass

    @staticmethod
    def _table_exists(connection, table: str) -> bool:
        return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

    @staticmethod
    def _serialize_vector(vector: list[float]) -> bytes:
        return struct.pack(f"{len(vector)}f", *vector)

    def _insert_vector(self, turn_id: int, initiative: str, vector: list[float]) -> None:
        # Kept as a compatibility hook; insertion is owned by the background worker.
        self._start_reindex()

    def recall(self, query: str, *, initiative: str, limit: int = 5) -> list[dict[str, str]]:
        if self.path is None or not self.vector_enabled or self.embedding_client is None:
            return []
        try:
            fingerprint = self._embedding_fingerprint()
            with self._connect() as connection:
                state_key = "vector_state_" + fingerprint
                metadata = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('vector_active_fingerprint',?)", (state_key,)))
            if metadata.get("vector_active_fingerprint") != fingerprint or metadata.get(state_key) != "ready":
                self._start_reindex()
                return []
            table = self._table_for_fingerprint(fingerprint)
            vector = self.embedding_client.embed(query)
            with self._connect() as connection:
                rows = connection.execute(
                    f"SELECT rowid AS id, distance FROM {table} WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                    (self._serialize_vector(vector), max(limit * 4, limit)),
                ).fetchall()
                by_id = {int(row["id"]): float(row["distance"]) for row in rows}
                if not by_id:
                    return []
                marks = ",".join("?" for _ in by_id)
                turns = connection.execute(
                    f"SELECT id,initiative,user_message,assistant_message FROM turns WHERE id IN ({marks})",
                    tuple(by_id),
                ).fetchall()
            turns = sorted(turns, key=lambda row: (row["initiative"] != initiative, by_id[int(row["id"])]))
            return [
                {"initiative": str(row["initiative"]), "user": str(row["user_message"]), "assistant": str(row["assistant_message"])}
                for row in turns[:limit]
            ]
        except Exception as error:
            self._set_vector_error(
                f"El endpoint de chat no admite embeddings o la búsqueda falló ({type(error).__name__}); el agente continúa sin recuerdos vectoriales."
            )
            return []

    def wait_for_reindex(self, timeout: float = 10.0) -> bool:
        thread = self._reindex_thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def list_records(self, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        if self.path is None:
            return {"calls": [], "turns": []}
        with self._connect() as connection:
            calls = [dict(row) for row in connection.execute("SELECT * FROM calls ORDER BY id DESC LIMIT ?", (limit,))]
            turns = [dict(row) for row in connection.execute("SELECT * FROM turns ORDER BY id DESC LIMIT ?", (limit,))]
        return {"calls": calls, "turns": turns}

    def export_jsonl(self) -> str:
        records = self.list_records(limit=1_000_000)
        lines = []
        for record in records["calls"]:
            lines.append(json.dumps({"type": "call", **record}, ensure_ascii=False))
        for record in records["turns"]:
            lines.append(json.dumps({"type": "turn", **record}, ensure_ascii=False))
        return "\n".join(lines) + ("\n" if lines else "")

    def clear(self) -> None:
        if self.path is None:
            return
        self._cancel_reindex.set()
        with self._vector_lock:
            with self._connect() as connection:
                connection.execute("DELETE FROM calls")
                connection.execute("DELETE FROM turns")
                vector_tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%USING vec0%' AND name LIKE 'memory_vectors%'")]
                for table in vector_tables:
                    connection.execute(f"DELETE FROM {table}")
                connection.execute("DELETE FROM metadata WHERE key LIKE 'vector_%'")
                connection.execute("DELETE FROM metadata WHERE key='embedding_test_fingerprint'")
        # A cancelled worker may still be waiting for its in-flight provider
        # request, but it will not write after observing the event. A later
        # turn can start a fresh worker immediately.
        self._reindex_thread = None
        legacy = self.path.parent / "sessions" / "latest.jsonl"
        try:
            legacy.unlink(missing_ok=True)
        except OSError:
            pass
