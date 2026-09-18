import json

from specnative_pilot.history import HistoryStore


def test_history_is_disabled_without_path(tmp_path):
    HistoryStore(None).append("user", message="secret")
    assert list(tmp_path.iterdir()) == []


def test_history_writes_jsonl(tmp_path):
    path = tmp_path / "sessions" / "latest.jsonl"
    HistoryStore(path).append("user", message="hello")
    record = json.loads(path.read_text().strip())
    assert record["event"] == "user"
    assert record["message"] == "hello"
