from types import SimpleNamespace

from specnative_pilot import agent_mcp_server
from specnative_pilot.session import SessionError


def test_mcp_session_failure_is_logged_without_writing_to_stdout(monkeypatch, capsys):
    logged = []

    class FakeManager:
        config = SimpleNamespace(model="test-model", api_base="https://api.example.test/v1")

        def __init__(self, config):
            pass

        def get(self, session_id):
            raise SessionError("Sesión inexistente.")

    monkeypatch.setattr(agent_mcp_server, "SessionManager", FakeManager)
    monkeypatch.setattr(agent_mcp_server, "record_failure", lambda *args, **kwargs: logged.append((args, kwargs)))
    server = agent_mcp_server.create_server(FakeManager.config)
    tool = server._tool_manager.get_tool("agent_session_status")

    result = tool.fn("missing-session")

    assert result["status"] == "error"
    assert logged[0][0][0] == "agent_mcp_status"
    assert logged[0][1]["model"] == "test-model"
    assert capsys.readouterr().out == ""
