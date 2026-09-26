from pathlib import Path

from specnative_pilot.config import load_config


def test_external_mcp_paths_override_local_config(tmp_path):
    config_file = tmp_path / "agent.toml"
    config_file.write_text(
        '[mcp]\npython = "local/python"\nscript = "local/mcp.py"\n',
        encoding="utf-8",
    )

    config = load_config(
        tmp_path,
        config_file,
        mcp_python=Path("external/python"),
        mcp_script=Path("external/mcp.py"),
    )

    assert config.mcp_python == tmp_path / "external/python"
    assert config.mcp_script == tmp_path / "external/mcp.py"


def test_default_mcp_is_bundled_and_does_not_require_agent_root(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECNATIVE_AGENT_ROOT", raising=False)
    config = load_config(tmp_path)

    assert config.mcp_python is None
    assert config.mcp_script is None


def test_partial_mcp_configuration_is_rejected(tmp_path):
    config_file = tmp_path / "agent.toml"
    config_file.write_text('[mcp]\npython = "local/python"\n', encoding="utf-8")

    try:
        load_config(tmp_path, config_file)
    except ValueError as error:
        assert "juntos" in str(error)
    else:
        raise AssertionError("partial MCP configuration should fail")


def test_local_mcp_takes_precedence_over_legacy_config(tmp_path):
    config_file = tmp_path / "agent.toml"
    config_file.write_text(
        '[mcp]\npython = "legacy/python"\nscript = "legacy/mcp.py"\n',
        encoding="utf-8",
    )
    local_script = tmp_path / ".specnative" / "specnative_mcp.py"
    local_script.parent.mkdir()
    local_script.write_text("# local\n", encoding="utf-8")

    config = load_config(tmp_path, config_file)

    assert config.mcp_python is None
    assert config.mcp_script is None


def test_reasoning_effort_uses_toml_unless_environment_overrides(tmp_path, monkeypatch):
    config_file = tmp_path / "agent.toml"
    config_file.write_text('[agent]\nreasoning_effort = "medium"\n', encoding="utf-8")
    monkeypatch.delenv("SPECNATIVE_AGENT_REASONING_EFFORT", raising=False)

    assert load_config(tmp_path, config_file).reasoning_effort == "medium"

    monkeypatch.setenv("SPECNATIVE_AGENT_REASONING_EFFORT", "low")
    assert load_config(tmp_path, config_file).reasoning_effort == "low"


def test_reasoning_effort_defaults_to_provider_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("SPECNATIVE_AGENT_REASONING_EFFORT", raising=False)

    assert load_config(tmp_path).reasoning_effort is None


def test_reasoning_effort_must_be_a_string_in_toml(tmp_path, monkeypatch):
    config_file = tmp_path / "agent.toml"
    config_file.write_text("[agent]\nreasoning_effort = 2\n", encoding="utf-8")
    monkeypatch.delenv("SPECNATIVE_AGENT_REASONING_EFFORT", raising=False)

    try:
        load_config(tmp_path, config_file)
    except ValueError as error:
        assert "reasoning_effort" in str(error)
    else:
        raise AssertionError("non-string reasoning_effort should fail")
