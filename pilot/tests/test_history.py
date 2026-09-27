import json

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

    def __init__(self):
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        return [float(len(text)), 0.25, 0.5]


def test_vector_memory_retrieves_same_repository_turns_and_prioritizes_initiative(tmp_path):
    embeddings = FakeEmbeddings()
    history = HistoryStore(tmp_path / "memory.sqlite3", embeddings)
    history.record_turn("wifi portal login", "Use a session flow", initiative="portal")
    history.record_turn("wifi portal page", "Check captive network", initiative="other")

    results = history.recall("wifi portal", initiative="portal", limit=2)

    assert len(results) == 2
    assert results[0]["initiative"] == "portal"
    assert len(embeddings.calls) >= 3


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
