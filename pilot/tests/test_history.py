import json
import sqlite3
import threading

from specnative_pilot.history import HistoryStore


def test_history_is_disabled_without_path(tmp_path):
    HistoryStore(None).append("user", message="secret")
    assert list(tmp_path.iterdir()) == []


def test_history_writes_visible_turn_to_sqlite(tmp_path):
    path = tmp_path / "agent" / "memory.sqlite3"
    history = HistoryStore(path)
    history.record_turn("hello", "hi", initiative="demo")
    record = history.list_records()["turns"][0]
    assert record["user_message"] == "hello"
    assert record["assistant_message"] == "hi"


def test_history_records_only_call_metadata(tmp_path):
    history = HistoryStore(tmp_path / "memory.sqlite3")
    history.record_call(
        model="model-a", endpoint="https://provider.test/v1", elapsed_ms=123.4,
        success=False, error_type="BadRequestError", status_code=400,
    )
    record = history.list_records()["calls"][0]
    assert record["model"] == "model-a"
    assert record["elapsed_ms"] == 123.4
    assert record["status_code"] == 400
    assert "request" not in record
    assert "response" not in record


def test_old_calls_schema_is_migrated_additively(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE calls (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, model TEXT, endpoint TEXT, elapsed_ms REAL NOT NULL, success INTEGER NOT NULL, error_type TEXT, status_code INTEGER, finish_reason TEXT)")
    history = HistoryStore(path)
    history.record_call(model="model", endpoint=None, elapsed_ms=1, success=True)
    call = history.list_records()["calls"][0]
    assert call["request_type"] == "chat"
    assert call["cached_tokens"] is None


def test_history_exports_and_clears_records(tmp_path):
    path = tmp_path / "agent" / "memory.sqlite3"
    history = HistoryStore(path)
    history.record_turn("question", "answer", initiative="demo")
    exported = history.export_jsonl()
    assert '"type": "turn"' in exported
    history.clear()
    assert history.list_records() == {"calls": [], "turns": []}


class FakeEmbeddings:
    model = "embedding-model"
    base_url = "https://embed.example.test/v1"

    def __init__(self):
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        return [float(len(text)), 0.25, 0.5]


def test_vector_index_requires_the_configured_endpoint_model_to_pass_diagnostic(tmp_path):
    embeddings = FakeEmbeddings()
    history = HistoryStore(tmp_path / "memory.sqlite3")
    assert not history.embedding_profile_was_tested(embeddings)
    history.mark_embedding_profile_tested(embeddings.model, embeddings.base_url)
    assert history.embedding_profile_was_tested(embeddings)
    embeddings.model = "different-model"
    assert not history.embedding_profile_was_tested(embeddings)


def test_vector_memory_retrieves_same_repository_turns_and_prioritizes_initiative(tmp_path):
    embeddings = FakeEmbeddings()
    history = HistoryStore(tmp_path / "memory.sqlite3", embeddings)
    history.record_turn("wifi portal login", "Use a session flow", initiative="portal")
    history.record_turn("wifi portal page", "Check captive network", initiative="other")
    assert history.wait_for_reindex()

    results = history.recall("wifi portal", initiative="portal", limit=2)

    assert len(results) == 2
    assert results[0]["initiative"] == "portal"
    assert len(embeddings.calls) >= 3


def test_reindexing_is_background_and_keeps_turn_history_on_embedding_error(tmp_path):
    class BrokenEmbeddings(FakeEmbeddings):
        def embed(self, text):
            raise RuntimeError("provider down")

    history = HistoryStore(tmp_path / "memory.sqlite3", BrokenEmbeddings())
    history.record_turn("question", "answer", initiative="demo")
    assert history.wait_for_reindex()
    assert len(history.list_records()["turns"]) == 1
    assert history.vector_error and "historial SQL se conserva" in history.vector_error


def test_embedding_profile_reindex_keeps_old_index_until_new_index_is_ready(tmp_path):
    history = HistoryStore(tmp_path / "memory.sqlite3", FakeEmbeddings())
    history.record_turn("question", "answer", initiative="demo")
    assert history.wait_for_reindex()
    previous_fingerprint = history._embedding_fingerprint()
    previous_table = history._table_for_fingerprint(previous_fingerprint)
    with history._connect() as connection:
        assert history._table_exists(connection, previous_table)

    entered = threading.Event()
    release = threading.Event()

    class SlowEmbeddings(FakeEmbeddings):
        model = "different-model"
        base_url = "https://other-embed.example.test/v1"

        def embed(self, text):
            entered.set()
            release.wait(timeout=3)
            return [0.3, 0.2, 0.1]

    history.configure_embeddings(SlowEmbeddings())
    assert entered.wait(timeout=3)
    assert history._embedding_fingerprint() != previous_fingerprint
    assert history.vector_error and "reconstruyendo" in history.vector_error
    assert history.recall("question", initiative="demo") == []
    with history._connect() as connection:
        assert history._table_exists(connection, previous_table)
        assert connection.execute("SELECT value FROM metadata WHERE key='vector_active_fingerprint'").fetchone()[0] == previous_fingerprint

    release.set()
    assert history.wait_for_reindex(timeout=5)
    assert len(history.list_records()["turns"]) == 1
    with history._connect() as connection:
        assert connection.execute("SELECT value FROM metadata WHERE key='vector_active_fingerprint'").fetchone()[0] == history._embedding_fingerprint()


def test_imports_legacy_jsonl_once_and_clear_removes_it(tmp_path):
    legacy = tmp_path / "agent" / "sessions" / "latest.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        '{"event":"user","timestamp":"2026-01-01T00:00:00Z","initiative":"demo","message":"old question"}\n'
        '{"event":"agent","timestamp":"2026-01-01T00:00:01Z","initiative":"demo","response":"old answer"}\n',
        encoding="utf-8",
    )
    history = HistoryStore(tmp_path / "agent" / "memory.sqlite3")
    assert len(history.list_records()["turns"]) == 1
    HistoryStore(tmp_path / "agent" / "memory.sqlite3")
    assert len(history.list_records()["turns"]) == 1
    history.clear()
    assert not legacy.exists()
