import sys

from specnative_pilot import mcp_launcher


def test_local_mcp_is_selected_before_remote_provider(tmp_path, monkeypatch):
    local_script = tmp_path / ".specnative" / "specnative_mcp.py"
    local_script.parent.mkdir()
    local_script.write_text("# local\n", encoding="utf-8")
    executed = {}

    def fake_execv(python, command):
        executed["python"] = python
        executed["command"] = command

    monkeypatch.setattr(sys, "argv", ["asn-mcp", "--repo", str(tmp_path)])
    monkeypatch.setattr(mcp_launcher.os, "execv", fake_execv)
    monkeypatch.setattr(mcp_launcher, "resolve_remote_mcp", lambda: (_ for _ in ()).throw(AssertionError("remote")))

    mcp_launcher.main()

    assert executed["python"] == sys.executable
    assert executed["command"][1] == str(local_script)
