from pathlib import Path

import pytest

from specnative_pilot.mcp import SpecNativeMcp


class Tool:
    def __init__(self, name):
        self.name = name

    def forward(self, **kwargs):
        return {"result": f"{self.name} ok"}


class Client:
    instances = []

    def __init__(self, params, structured_output=True):
        self.params = params
        self.closed = False
        self.instances.append(self)

    def __enter__(self):
        if any("mcp_server" in value for value in self.params.args):
            return [Tool(name) for name in ("write_spec", "write_tasks", "validate", "health_check")]
        return [Tool("read_spec"), Tool("validate")]

    def __exit__(self, *_):
        self.closed = True


def test_approved_write_uses_bundled_mcp_only_when_project_lacks_write_tools(tmp_path, monkeypatch):
    Client.instances = []
    monkeypatch.setattr("specnative_pilot.mcp.MCPClient", Client)
    mcp = SpecNativeMcp(Path(tmp_path))
    mcp.__enter__()
    assert {tool.name for tool in mcp.read_tools} == {"read_spec", "validate"}
    with mcp.approved_calls({"write_spec", "validate", "health_check"}) as call:
        assert call("write_spec", initiative="demo", content="# Spec") == "write_spec ok"
        assert call("validate") == "validate ok"
        with pytest.raises(RuntimeError, match="no fue declarada"):
            call("write_tasks", initiative="demo", content="# Tasks")
    assert mcp.approval_backend == "MCP incluido con ASN"
    assert "specnative_pilot.mcp_server" in Client.instances[1].params.args
    mcp.__exit__(None, None, None)
    assert all(client.closed for client in Client.instances)


def test_project_mcp_is_used_when_it_has_all_approved_tools(tmp_path, monkeypatch):
    class FullClient(Client):
        instances = []

        def __enter__(self):
            return [Tool(name) for name in ("write_spec", "validate", "health_check")]

    monkeypatch.setattr("specnative_pilot.mcp.MCPClient", FullClient)
    mcp = SpecNativeMcp(Path(tmp_path))
    mcp.__enter__()
    with mcp.approved_calls({"write_spec", "validate", "health_check"}) as call:
        assert call("write_spec", initiative="demo", content="# Spec") == "write_spec ok"
    assert mcp.approval_backend == "MCP del proyecto"
    assert len(FullClient.instances) == 1
    mcp.__exit__(None, None, None)
