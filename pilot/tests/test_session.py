from __future__ import annotations

from pathlib import Path

import pytest

from specnative_pilot.config import Config
from specnative_pilot.models import Proposal
from specnative_pilot.session import AgentSession, SessionError, SessionManager


class FakeMcp:
    def __init__(self, validation="Validation passed"):
        self.validation = validation
        self.calls = []
        self.read_tools = []

    def call(self, name, **arguments):
        self.calls.append((name, arguments))
        if name == "validate":
            return self.validation
        if name == "health_check":
            return "Health check passed"
        if name == "context_snapshot":
            return "context"
        if name == "list_templates":
            return "     feature-rest-endpoint          Nueva ruta\n"
        if name == "write_spec":
            return "SPEC written"
        if name == "write_tasks":
            return "TASKS written"
        if name == "apply_spec_template":
            return "template applied"
        if name == "list_specs":
            return "initiative-a"
        return "ok"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class FakeAgent:
    def __init__(self, *_):
        self.proposals = []

    def run_turn(self, message, context):
        self.proposals = [Proposal("demo", "spec", "Resumen", "content", "rationale", ["SPEC.md"])]
        return f"response: {message}"


def config(tmp_path: Path, history: bool = False) -> Config:
    return Config(tmp_path, "model", None, "OPENAI_API_KEY", "single", history, 2, None, None)


def session(tmp_path, monkeypatch):
    monkeypatch.setattr("specnative_pilot.session.SpecNativeAgent", FakeAgent)
    return AgentSession.from_mcp(config(tmp_path), "demo", FakeMcp(), model_builder=lambda _: object())


def test_message_returns_proposal_without_writing(tmp_path, monkeypatch):
    current = session(tmp_path, monkeypatch)
    result = current.message("idea")
    assert result["status"] == "approval_required"
    assert not [call for call in current.mcp.calls if call[0].startswith("write_")]

    applied = current.approve(result["approval_token"])
    assert applied["status"] == "applied"
    assert [call[0] for call in current.mcp.calls] == [
        "context_snapshot", "write_spec", "validate", "health_check"
    ]


def test_reject_does_not_write_and_stale_token_fails(tmp_path, monkeypatch):
    current = session(tmp_path, monkeypatch)
    result = current.message("idea")
    rejected = current.reject(result["approval_token"])
    assert rejected["status"] == "rejected"
    assert not [call for call in current.mcp.calls if call[0] == "write_spec"]
    with pytest.raises(SessionError, match="Token"):
        current.approve(result["approval_token"])


def test_template_requires_explicit_command_and_approval(tmp_path, monkeypatch):
    current = session(tmp_path, monkeypatch)
    normal = current.message("usa una plantilla feature-rest-endpoint")
    assert normal["status"] == "approval_required"
    assert normal["action"] == "proposals"
    current.reject(normal["approval_token"])

    invalid = current.message("/template missing")
    assert invalid["status"] == "template_invalid"
    assert not [call for call in current.mcp.calls if call[0] == "apply_spec_template"]

    valid = current.message("/template feature-rest-endpoint")
    assert valid["action"] == "template"
    current.approve(valid["approval_token"])
    assert [call[0] for call in current.mcp.calls if call[0] == "apply_spec_template"] == [
        "apply_spec_template"
    ]


def test_manager_reports_preflight_without_building_model(tmp_path, monkeypatch):
    class InvalidMcp(FakeMcp):
        def __init__(self, *args, **kwargs):
            super().__init__("Validation failed: missing context")

    monkeypatch.setattr("specnative_pilot.session.SpecNativeMcp", InvalidMcp)
    monkeypatch.setattr("specnative_pilot.session.build_model", lambda _: pytest.fail("model built"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = SessionManager(config(tmp_path)).start("demo")
    assert result["status"] == "preflight_failed"


def test_manager_reports_missing_credentials_with_auth_command(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("specnative_pilot.session.SpecNativeMcp", lambda *_: pytest.fail("MCP must not start"))
    result = SessionManager(config(tmp_path)).start("demo")
    assert result["status"] == "credentials_missing"
    assert "OPENAI_API_KEY" in result["text"]
    assert "asn --auth" in result["text"]
