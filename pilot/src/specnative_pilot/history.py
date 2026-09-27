from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import struct
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmbeddingClient:
    """OpenAI-compatible embedding client sharing ASN's configured endpoint/key."""

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None) -> None:
        from openai import OpenAI

        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, text: str) -> list[float]:
        result = self.client.embeddings.create(model=self.model, input=text)
        return list(result.data[0].embedding)


class HistoryStore:
    """Per-repository SQLite call history and visible conversation memory."""

    def __init__(self, path: Path | None, embedding_client: EmbeddingClient | None = None) -> None:
        self.path = path
        self.embedding_client = embedding_client
        self.vector_error: str | None = None
        self.vector_enabled = embedding_client is not None
        self._sqlite_vec: Any = None
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
                        finish_reason TEXT
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
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass
            self._import_legacy_jsonl()

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
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO turns(timestamp,session_id,initiative,user_message,assistant_message) VALUES(?,?,?,?,?)",
                (_now(), session_id, initiative, user_message, assistant_message),
            )
            turn_id = int(cursor.lastrowid)
        self._index_turn(turn_id, initiative, user_message, assistant_message)

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
    ) -> None:
        if self.path is None:
            return
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO calls(timestamp,model,endpoint,elapsed_ms,success,error_type,status_code,finish_reason) VALUES(?,?,?,?,?,?,?,?)",
                (_now(), model, endpoint, max(0.0, float(elapsed_ms)), int(success), error_type, status_code, finish_reason),
            )

    def _set_vector_error(self, message: str) -> None:
        self.vector_enabled = False
        self.vector_error = message

    def _index_turn(self, turn_id: int, initiative: str, user_message: str, assistant_message: str) -> None:
        if not self.vector_enabled or self.embedding_client is None or self.path is None:
            return
        try:
            vector = self.embedding_client.embed(f"Usuario: {user_message}\nAgente: {assistant_message}")
            self._insert_vector(turn_id, initiative, vector)
        except Exception as error:
            self._set_vector_error(
                f"El endpoint de chat no pudo crear embeddings ({type(error).__name__}); se conserva el historial sin búsqueda vectorial."
            )

    @staticmethod
    def _serialize_vector(vector: list[float]) -> bytes:
        return struct.pack(f"{len(vector)}f", *vector)

    def _insert_vector(self, turn_id: int, initiative: str, vector: list[float]) -> None:
        if self.path is None or self._sqlite_vec is None:
            return
        with self._connect() as connection:
            meta = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('vector_dimension','embedding_model')"))
            dimension = len(vector)
            model_name = self.embedding_client.model if self.embedding_client else ""
            if "memory_vectors" in {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                if meta.get("vector_dimension") != str(dimension) or meta.get("embedding_model") != model_name:
                    connection.execute("DROP TABLE memory_vectors")
                    connection.execute("DELETE FROM metadata WHERE key IN ('vector_dimension','embedding_model')")
            exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_vectors'").fetchone()
            if not exists:
                connection.execute(f"CREATE VIRTUAL TABLE memory_vectors USING vec0(embedding float[{dimension}], +initiative TEXT)")
                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_dimension',?)", (str(dimension),))
                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_model',?)", (model_name,))
                rows = connection.execute("SELECT id,initiative,user_message,assistant_message FROM turns WHERE id != ?", (turn_id,)).fetchall()
            else:
                rows = []
            connection.execute(
                "INSERT OR REPLACE INTO memory_vectors(rowid,embedding,initiative) VALUES(?,?,?)",
                (turn_id, self._serialize_vector(vector), initiative),
            )
        for row in rows:
            try:
                prior = self.embedding_client.embed(f"Usuario: {row['user_message']}\nAgente: {row['assistant_message']}")
                if len(prior) == len(vector):
                    with self._connect() as connection:
                        connection.execute(
                            "INSERT OR REPLACE INTO memory_vectors(rowid,embedding,initiative) VALUES(?,?,?)",
                            (row["id"], self._serialize_vector(prior), row["initiative"]),
                        )
            except Exception as error:
                self._set_vector_error(f"No se pudo reconstruir el índice vectorial ({type(error).__name__}).")
                return

    def recall(self, query: str, *, initiative: str, limit: int = 5) -> list[dict[str, str]]:
        if self.path is None or not self.vector_enabled or self.embedding_client is None:
            return []
        try:
            vector = self.embedding_client.embed(query)
            self._ensure_legacy_vectors(vector)
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT rowid AS id, distance FROM memory_vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
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

    def _ensure_legacy_vectors(self, query_vector: list[float]) -> None:
        if self.path is None or self._sqlite_vec is None:
            return
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_vectors'"
            ).fetchone()
            metadata = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('vector_dimension','embedding_model')"))
            model_name = self.embedding_client.model if self.embedding_client else ""
            if exists and (
                metadata.get("vector_dimension") != str(len(query_vector))
                or metadata.get("embedding_model") != model_name
            ):
                connection.execute("DROP TABLE memory_vectors")
                connection.execute("DELETE FROM metadata WHERE key IN ('vector_dimension','embedding_model')")
                exists = None
            if not exists:
                dimension = len(query_vector)
                connection.execute(f"CREATE VIRTUAL TABLE memory_vectors USING vec0(embedding float[{dimension}], +initiative TEXT)")
                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('vector_dimension',?)", (str(dimension),))
                connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('embedding_model',?)", (model_name,))
                indexed = 0
            else:
                indexed = connection.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0]
            total = connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            missing = connection.execute(
                "SELECT id,initiative,user_message,assistant_message FROM turns ORDER BY id LIMIT ?", (max(0, total - indexed),)
            ).fetchall() if total > indexed else []
        for row in missing:
            self._index_turn(int(row["id"]), str(row["initiative"]), str(row["user_message"]), str(row["assistant_message"]))

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
        with self._connect() as connection:
            connection.execute("DELETE FROM calls")
            connection.execute("DELETE FROM turns")
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_vectors'").fetchone():
                connection.execute("DELETE FROM memory_vectors")
        legacy = self.path.parent / "sessions" / "latest.jsonl"
        try:
            legacy.unlink(missing_ok=True)
        except OSError:
            pass
