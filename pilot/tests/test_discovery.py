from pathlib import Path

from specnative_pilot.mcp_discovery import find_local_mcp, resolve_project_repo


def test_finds_mcp_in_current_project(tmp_path):
    script = tmp_path / ".specnative" / "specnative_mcp.py"
    script.parent.mkdir()
    script.write_text("# local\n", encoding="utf-8")

    assert find_local_mcp(tmp_path) == script
    assert resolve_project_repo(tmp_path / "src") == tmp_path


def test_finds_nearest_mcp_in_parent(tmp_path):
    script = tmp_path / ".specnative" / "specnative_mcp.py"
    script.parent.mkdir()
    script.write_text("# local\n", encoding="utf-8")
    nested = tmp_path / "src" / "feature"
    nested.mkdir(parents=True)

    assert find_local_mcp(nested) == script


def test_missing_mcp_keeps_explicit_start_as_project(tmp_path):
    nested = tmp_path / "src"
    nested.mkdir()

    assert find_local_mcp(nested) is None
    assert resolve_project_repo(nested) == nested
