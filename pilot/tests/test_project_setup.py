from __future__ import annotations

import json

import pytest

from specnative_pilot.project_setup import setup_project


def test_setup_creates_all_client_integrations_without_justfile(tmp_path):
    justfile = tmp_path / "Justfile"
    justfile.write_text("test:\n    echo ok\n", encoding="utf-8")
    changed = setup_project(tmp_path, {"codex", "claude", "opencode"})
    assert justfile.read_text(encoding="utf-8") == "test:\n    echo ok\n"
    assert (tmp_path / ".codex/skills/specnative-agent/SKILL.md").exists()
    assert (tmp_path / ".claude/skills/specnative-agent/SKILL.md").exists()
    assert (tmp_path / ".opencode/skills/specnative-agent/SKILL.md").exists()
    assert (tmp_path / ".mcp.json").exists()
    assert (tmp_path / "opencode.json").exists()
    assert any(path.name == "config.toml" for path in changed)

    assert setup_project(tmp_path, {"codex", "claude", "opencode"}) == []


def test_setup_merges_both_mcp_servers(tmp_path):
    setup_project(tmp_path, {"claude", "opencode"})
    claude = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    opencode = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert set(claude["mcpServers"]) == {"asn-agent", "specnative"}
    assert set(opencode["mcp"]["servers"]) == {"asn-agent", "specnative"}
    assert claude["mcpServers"]["asn-agent"]["command"] == "asn-agent-mcp"


def test_setup_rejects_skill_collision_before_writing_other_files(tmp_path):
    skill = tmp_path / ".codex/skills/specnative-agent/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("different", encoding="utf-8")
    with pytest.raises(ValueError, match="no coincide"):
        setup_project(tmp_path, {"codex", "claude"})
    assert not (tmp_path / ".mcp.json").exists()
