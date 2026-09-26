from pathlib import Path

from specnative_pilot import model
from specnative_pilot.config import Config
from specnative_pilot.secrets import ResolvedCredentials


def _config(reasoning_effort):
    return Config(
        repo=Path("."),
        model="groq-model",
        api_base="https://api.example.test/v1",
        api_key_env="OPENAI_API_KEY",
        question_mode="single",
        history=False,
        max_steps=12,
        mcp_python=None,
        mcp_script=None,
        reasoning_effort=reasoning_effort,
    )


def test_build_model_passes_configured_reasoning_effort(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(model, "resolve_credentials", lambda config: ResolvedCredentials("groq-model", "https://api.example.test/v1", "key"))
    monkeypatch.setattr(model, "OpenAIServerModel", fake_model)

    model.build_model(_config("low"))

    assert captured["reasoning_effort"] == "low"


def test_build_model_omits_reasoning_effort_when_unset(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(model, "resolve_credentials", lambda config: ResolvedCredentials("groq-model", None, "key"))
    monkeypatch.setattr(model, "OpenAIServerModel", fake_model)

    model.build_model(_config(None))

    assert "reasoning_effort" not in captured
