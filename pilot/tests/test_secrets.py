from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from specnative_pilot.config import load_config
from specnative_pilot.secret_setup import SecretToolsMissingError, authenticate, initialize_secrets
from specnative_pilot.secrets import (
    SecretResolutionError,
    global_sops_file,
    resolve_credentials,
)


def _result(stdout: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


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


def test_global_sops_is_used_when_project_has_no_secret_file(tmp_path, monkeypatch):
    global_file = global_sops_file()
    global_file.parent.mkdir(parents=True)
    global_file.write_text("encrypted", encoding="utf-8")
    monkeypatch.setenv("SPECNATIVE_AGENT_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return _result(json.dumps({"model": "global-model", "api_key": "global-key"}))

    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("specnative_pilot.secrets.subprocess.run", fake_run)
    credentials = resolve_credentials(load_config(tmp_path))
    assert credentials.model == "global-model"
    assert credentials.api_key == "global-key"
    assert calls[0][-1] == str(global_file)


def test_sops_decryption_uses_asn_age_identity_when_present(tmp_path, monkeypatch):
    secret_file = tmp_path / ".specnative/agent.secrets.yaml"
    secret_file.parent.mkdir()
    secret_file.write_text("encrypted", encoding="utf-8")
    identity = tmp_path / ".age/asn-key.txt"
    identity.parent.mkdir()
    identity.write_text("AGE-SECRET-KEY-test", encoding="utf-8")
    monkeypatch.setattr("specnative_pilot.secrets.AGE_IDENTITY_FILE", identity)
    captured = {}
    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return _result(json.dumps({"model": "model", "api_key": "key"}))

    monkeypatch.setattr("specnative_pilot.secrets.subprocess.run", fake_run)
    resolve_credentials(load_config(tmp_path))
    assert captured["env"]["SOPS_AGE_KEY_FILE"] == str(identity)


def test_project_secrets_take_precedence_over_global_sops(tmp_path, monkeypatch):
    project_file = tmp_path / ".specnative/agent.secrets.yaml"
    project_file.parent.mkdir()
    project_file.write_text("project encrypted", encoding="utf-8")
    global_file = global_sops_file()
    global_file.parent.mkdir(parents=True)
    global_file.write_text("global encrypted", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return _result(json.dumps({"model": "project-model", "api_key": "project-key"}))

    monkeypatch.setattr("specnative_pilot.secrets.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr("specnative_pilot.secrets.subprocess.run", fake_run)
    assert resolve_credentials(load_config(tmp_path)).model == "project-model"
    assert calls[0][-1] == str(project_file)


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
        "/bin/sops",
        "encrypt",
        "--input-type",
        "json",
        "--output-type",
        "yaml",
        "--filename-override",
        str(tmp_path / ".specnative/agent.secrets.yaml"),
        "/dev/stdin",
    ]
    assert "secret-key" in calls[0][1]["input"]


def test_auth_creates_global_sops_file_and_age_identity(tmp_path, monkeypatch):
    identity = tmp_path / ".age/asn-key.txt"
    monkeypatch.setattr("specnative_pilot.secret_setup.AGE_IDENTITY_FILE", identity)
    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda name: f"/bin/{name}")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1:2] == ["-o"]:
            Path(command[2]).write_text("AGE-SECRET-KEY-test\n", encoding="utf-8")
            return _result()
        if command[1:2] == ["-y"]:
            return _result("age1recipient\n")
        return _result("sops: encrypted output\n")

    monkeypatch.setattr("specnative_pilot.secret_setup.subprocess.run", fake_run)
    changed, cancelled = authenticate(
        None,
        confirm_replace=lambda _: pytest.fail("new auth must not ask to replace"),
        input_fn=lambda prompt: "model-id" if prompt == "Modelo: " else "https://api.example/v1",
        secret_input_fn=lambda _: "api-secret",
    )
    target = global_sops_file()
    assert not cancelled
    assert changed == [target]
    assert target.read_text(encoding="utf-8") == "sops: encrypted output\n"
    assert "api-secret" not in target.read_text(encoding="utf-8")
    assert identity.read_text(encoding="utf-8") == "AGE-SECRET-KEY-test\n"
    assert identity.stat().st_mode & 0o777 == 0o600
    encrypt_call = calls[-1]
    assert "--age" in encrypt_call[0]
    assert "age1recipient" in encrypt_call[0]
    assert encrypt_call[1]["env"]["SOPS_AGE_KEY_FILE"] == str(identity)
    assert "api-secret" in encrypt_call[1]["input"]


def test_auth_can_write_project_scoped_credentials(tmp_path, monkeypatch):
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-test\n", encoding="utf-8")
    monkeypatch.setattr("specnative_pilot.secret_setup.AGE_IDENTITY_FILE", identity)
    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        "specnative_pilot.secret_setup.subprocess.run",
        lambda command, **kwargs: _result("age1recipient\n") if "-y" in command else _result("encrypted\n"),
    )
    changed, cancelled = authenticate(
        tmp_path,
        confirm_replace=lambda _: False,
        input_fn=lambda _: "model",
        secret_input_fn=lambda _: "key",
    )
    assert not cancelled
    assert tmp_path / ".specnative/agent.secrets.yaml" in changed
    assert tmp_path / ".specnative/agent.toml" in changed
    assert 'backend = "sops"' in (tmp_path / ".specnative/agent.toml").read_text(encoding="utf-8")


def test_auth_replacement_requires_confirmation(tmp_path, monkeypatch):
    global_file = global_sops_file()
    global_file.parent.mkdir(parents=True)
    global_file.write_text("old encrypted data", encoding="utf-8")
    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda _: pytest.fail("must not check tools"))
    changed, cancelled = authenticate(
        None,
        confirm_replace=lambda _: False,
        input_fn=lambda _: pytest.fail("must not prompt for credentials"),
        secret_input_fn=lambda _: pytest.fail("must not prompt for API key"),
    )
    assert cancelled
    assert changed == []
    assert global_file.read_text(encoding="utf-8") == "old encrypted data"


def test_auth_replaces_existing_global_file_after_confirmation(tmp_path, monkeypatch):
    global_file = global_sops_file()
    global_file.parent.mkdir(parents=True)
    global_file.write_text("old encrypted data", encoding="utf-8")
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-test", encoding="utf-8")
    monkeypatch.setattr("specnative_pilot.secret_setup.AGE_IDENTITY_FILE", identity)
    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        "specnative_pilot.secret_setup.subprocess.run",
        lambda command, **kwargs: _result("age1recipient\n") if "-y" in command else _result("new encrypted data\n"),
    )
    changed, cancelled = authenticate(
        None,
        confirm_replace=lambda _: True,
        input_fn=lambda _: "model",
        secret_input_fn=lambda _: "key",
    )
    assert not cancelled
    assert changed == [global_file]
    assert global_file.read_text(encoding="utf-8") == "new encrypted data\n"


def test_auth_missing_tools_reports_install_guidance(tmp_path, monkeypatch):
    monkeypatch.setattr("specnative_pilot.secret_setup.shutil.which", lambda name: None if name == "sops" else f"/bin/{name}")
    with pytest.raises(SecretToolsMissingError, match="Instálalos y vuelve a ejecutar `asn --auth`"):
        authenticate(None, confirm_replace=lambda _: False)
