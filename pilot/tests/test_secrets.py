from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from specnative_pilot.config import load_config
from specnative_pilot.secret_setup import initialize_secrets
from specnative_pilot.secrets import SecretResolutionError, resolve_credentials


def _result(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_environment_is_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECNATIVE_AGENT_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    credentials = resolve_credentials(load_config(tmp_path))
    assert credentials.model == "env-model"
    assert credentials.api_key == "env-key"


def test_sops_provider_overrides_environment_without_writing_plaintext(tmp_path, monkeypatch):
    secret_file = tmp_path / ".specnative/agent.secrets.yaml"
    secret_file.parent.mkdir()
    secret_file.write_text("encrypted", encoding="utf-8")
    monkeypatch.setenv("SPECNATIVE_AGENT_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return _result(json.dumps({"model": "sops-model", "api_base": "https://sops", "api_key": "sops-key"}))

    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("specnative_pilot.secrets.subprocess.run", fake_run)
    credentials = resolve_credentials(load_config(tmp_path))
    assert credentials.model == "sops-model"
    assert credentials.api_base == "https://sops"
    assert credentials.api_key == "sops-key"
    assert commands[0][:2] == ["/bin/sops", "decrypt"]


def test_invalid_sops_does_not_fallback_to_environment(tmp_path, monkeypatch):
    secret_file = tmp_path / ".specnative/agent.secrets.yaml"
    secret_file.parent.mkdir()
    secret_file.write_text("invalid", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("specnative_pilot.secrets.subprocess.run", lambda *args, **kwargs: _result(returncode=1))
    with pytest.raises(SecretResolutionError, match="SOPS no pudo"):
        resolve_credentials(load_config(tmp_path))


def test_gopass_provider_reads_only_declared_references(tmp_path, monkeypatch):
    refs = tmp_path / ".specnative/agent.gopass.toml"
    refs.parent.mkdir()
    refs.write_text(
        '[references]\nmodel = "specnative/demo/model"\napi_key = "specnative/demo/api-key"\n',
        encoding="utf-8",
    )
    calls = []
    values = {"specnative/demo/model": "gopass-model\n", "specnative/demo/api-key": "gopass-key\n"}

    def fake_run(command, **kwargs):
        calls.append(command)
        return _result(values[command[-1]])

    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("specnative_pilot.secrets.subprocess.run", fake_run)
    credentials = resolve_credentials(load_config(tmp_path))
    assert credentials.model == "gopass-model"
    assert credentials.api_key == "gopass-key"
    assert all(command[:3] == ["/bin/gopass", "show", "--password-only"] for command in calls)


def test_sops_is_autodetected_before_gopass(tmp_path, monkeypatch):
    sops_file = tmp_path / ".specnative/agent.secrets.yaml"
    gopass_file = tmp_path / ".specnative/agent.gopass.toml"
    sops_file.parent.mkdir()
    sops_file.write_text("encrypted", encoding="utf-8")
    gopass_file.write_text('[references]\napi_key = "wrong"\n', encoding="utf-8")
    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        "specnative_pilot.secrets.subprocess.run",
        lambda command, **kwargs: _result(json.dumps({"api_key": "sops-key"})),
    )
    assert resolve_credentials(load_config(tmp_path)).api_key == "sops-key"


def test_none_backend_uses_environment_even_when_files_exist(tmp_path, monkeypatch):
    secret_file = tmp_path / ".specnative/agent.secrets.yaml"
    secret_file.parent.mkdir()
    secret_file.write_text("encrypted", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    config = load_config(tmp_path, secrets_backend="none")
    assert resolve_credentials(config).api_key == "env-key"


def test_gopass_init_creates_references_and_does_not_store_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda name: f"/bin/{name}")
    changed, instructions = initialize_secrets(tmp_path, "gopass", prefix="specnative/demo")
    assert (tmp_path / ".specnative/agent.gopass.toml").exists()
    content = (tmp_path / ".specnative/agent.gopass.toml").read_text(encoding="utf-8")
    assert "api-key" in content
    assert "[secrets]" in (tmp_path / ".specnative/agent.toml").read_text(encoding="utf-8")
    assert instructions == [
        "gopass insert specnative/demo/model",
        "gopass insert specnative/demo/api-base",
        "gopass insert specnative/demo/api-key",
    ]


def test_sops_init_encrypts_in_memory_and_updates_config(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return _result("sops: encrypted output\n")

    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("specnative_pilot.secret_setup.subprocess.run", fake_run)
    changed, instructions = initialize_secrets(
        tmp_path,
        "sops",
        input_fn=lambda prompt: "model" if prompt == "Modelo: " else "https://api",
        secret_input_fn=lambda prompt: "secret-key",
    )
    assert instructions == []
    assert (tmp_path / ".specnative/agent.secrets.yaml").read_text(encoding="utf-8") == "sops: encrypted output\n"
    assert "secret-key" not in (tmp_path / ".specnative/agent.secrets.yaml").read_text(encoding="utf-8")
    assert calls[0][0] == [
        "sops",
        "encrypt",
        "--input-type",
        "json",
        "--output-type",
        "yaml",
        "--filename-override",
        str(tmp_path / ".specnative/agent.secrets.yaml"),
    ]
    assert "secret-key" in calls[0][1]["input"]
