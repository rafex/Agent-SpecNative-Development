import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from specnative_pilot.model_eval import ModelEvalLog, TracingOpenAIClient


class _Response:
    def model_dump(self, mode="python"):
        return {
            "choices": [{"message": {"role": "assistant", "content": "respuesta", "reasoning": "razonamiento"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        }


def _events(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_model_eval_log_creates_private_temporary_jsonl(tmp_path):
    log = ModelEvalLog(tmp_path / "eval")

    assert log.path == tmp_path / "eval" / "model-calls.jsonl"
    assert log.path.exists()
    assert os.stat(log.directory).st_mode & 0o777 == 0o700
    assert os.stat(log.path).st_mode & 0o777 == 0o600


def test_tracing_client_logs_exact_request_response_effort_and_latency(tmp_path):
    received = []

    class Completions:
        def create(self, **kwargs):
            received.append(kwargs)
            return _Response()

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    log = ModelEvalLog(tmp_path / "eval")
    traced = TracingOpenAIClient(client, log, "openai/gpt-oss-120b", "https://api.groq.com/openai/v1")
    request = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "idea exacta"}],
        "tools": [{"type": "function", "function": {"name": "lookup"}}],
        "tool_choice": "required",
        "reasoning_effort": "low",
    }

    result = traced.chat.completions.create(**request)

    event = _events(log.path)[0]
    assert result is not None
    assert received == [request]
    assert event["request"] == request
    assert event["response"] == _Response().model_dump(mode="json")
    assert event["model"] == "openai/gpt-oss-120b"
    assert event["reasoning_effort"] == "low"
    assert event["elapsed_ms"] >= 0
    assert event["endpoint"] == "https://api.groq.com/openai/v1"


def test_tracing_client_does_not_record_auth_headers_and_logs_provider_error(tmp_path):
    token = "secret-test-token"

    class ProviderError(RuntimeError):
        status_code = 400
        body = {"error": {"message": "model did not call a tool"}}

    class Completions:
        def create(self, **kwargs):
            raise ProviderError("400 model did not call a tool")

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    log = ModelEvalLog(tmp_path / "eval")
    traced = TracingOpenAIClient(client, log, "test-model", "https://api.example.test/v1?token=private")

    with pytest.raises(ProviderError):
        traced.chat.completions.create(
            model="test-model",
            messages=[{"role": "user", "content": "unredacted eval prompt"}],
            extra_headers={"Authorization": f"Bearer {token}"},
        )

    rendered = log.path.read_text(encoding="utf-8")
    event = _events(log.path)[0]
    assert event["request"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "unredacted eval prompt"}],
    }
    assert event["response"] == ProviderError.body
    assert event["error"]["status_code"] == 400
    assert event["endpoint"] == "https://api.example.test/v1?token=%5BOCULTO%5D"
    assert token not in rendered
