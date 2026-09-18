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


def test_agent_root_provides_external_mcp_defaults(tmp_path, monkeypatch):
    agent_root = tmp_path / "agent"
    monkeypatch.setenv("SPECNATIVE_AGENT_ROOT", str(agent_root))

    config = load_config(tmp_path)

    assert config.mcp_python == agent_root / ".specnative/.venv/bin/python"
    assert config.mcp_script == agent_root / ".specnative/specnative_mcp.py"
