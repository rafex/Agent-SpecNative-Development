from pathlib import Path
from types import SimpleNamespace

import pytest
from smolagents import Model, Tool, ToolCallingAgent
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
)

from specnative_pilot.config import Config
from specnative_pilot.mcp_check import AgentMcpTestError, check_agent_mcp


def _tool_call(name, arguments):
    return ChatMessageToolCall(
        function=ChatMessageToolCallFunction(name=name, arguments=arguments),
        id=f"call-{name}",
        type="function",
    )


class SequenceModel(Model):
    def __init__(self, responses, eval_path):
        super().__init__(model_id="mock-model")
        self.responses = iter(responses)
        self.eval_log = SimpleNamespace(request_count=0)
        self.eval_log_path = eval_path

    def generate(self, messages, **kwargs):
        self.eval_log.request_count += 1
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


class StatusTool(Tool):
    name = "status"
    description = "Return the SpecNative project status."
    inputs = {}
    output_type = "string"

    def __init__(self, error=None):
        self.is_initialized = True
        self.called = 0
        self.error = error

    def forward(self):
        self.called += 1
        if self.error:
            raise self.error
        return "SpecNative status: healthy"


class FakeMcp:
    def __init__(self, tools):
        self.read_tools = tools

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def config(tmp_path):
    return Config(
        repo=tmp_path,
        model="mock-model",
        api_base="https://provider.example/v1",
        api_key_env="OPENAI_API_KEY",
        question_mode="single",
        history=False,
        max_steps=12,
        mcp_python=None,
        mcp_script=None,
    )


def _responses(*extra):
    return [
        ChatMessage(
            role=MessageRole.ASSISTANT,
            tool_calls=[_tool_call("status", {})],
        ),
        *extra,
        ChatMessage(
            role=MessageRole.ASSISTANT,
            tool_calls=[_tool_call("final_answer", {"answer": "ASN_MCP_OK"})],
        ),
    ]


def test_agent_mcp_check_executes_read_tool_and_continues(tmp_path):
    eval_path = tmp_path / "model-calls.jsonl"
    model = SequenceModel(_responses(), eval_path)
    status = StatusTool()
    mcp = FakeMcp([status])

    result = check_agent_mcp(
        config(tmp_path),
        model_builder=lambda _: model,
        mcp_factory=lambda *_: mcp,
    )

    assert status.called == 1
    assert result.model == "mock-model"
    assert result.request_count == 2
    assert result.eval_log_path == eval_path


def test_agent_mcp_check_does_not_expose_write_tools(tmp_path, monkeypatch):
    model = SequenceModel(_responses(), tmp_path / "eval.jsonl")
    status = StatusTool()
    registered_tools = []
    original = ToolCallingAgent.__init__

    def capture_tools(self, *args, **kwargs):
        registered_tools.extend(kwargs["tools"])
        original(self, *args, **kwargs)

    monkeypatch.setattr(ToolCallingAgent, "__init__", capture_tools)
    check_agent_mcp(
        config(tmp_path),
        model_builder=lambda _: model,
        mcp_factory=lambda *_: FakeMcp([status, SimpleNamespace(name="write_spec")]),
    )

    assert [tool.name for tool in registered_tools] == ["status"]


def test_agent_mcp_check_reports_missing_status_tool(tmp_path):
    model = SequenceModel([], tmp_path / "eval.jsonl")

    with pytest.raises(AgentMcpTestError, match="no anuncia.*status") as error:
        check_agent_mcp(
            config(tmp_path),
            model_builder=lambda _: model,
            mcp_factory=lambda *_: FakeMcp([]),
        )

    assert error.value.stage == "MCP discovery"
    assert model.eval_log.request_count == 0


def test_agent_mcp_check_classifies_failure_before_tool_call(tmp_path):
    model = SequenceModel([RuntimeError("provider unavailable")], tmp_path / "eval.jsonl")

    with pytest.raises(AgentMcpTestError) as error:
        check_agent_mcp(
            config(tmp_path),
            model_builder=lambda _: model,
            mcp_factory=lambda *_: FakeMcp([StatusTool()]),
        )

    assert error.value.stage == "tool calling del modelo"
    assert error.value.request_count == 1


def test_agent_mcp_check_classifies_failure_after_tool_result(tmp_path):
    model = SequenceModel(
        _responses(RuntimeError("provider unavailable")),
        tmp_path / "eval.jsonl",
    )
    status = StatusTool()

    with pytest.raises(AgentMcpTestError) as error:
        check_agent_mcp(
            config(tmp_path),
            model_builder=lambda _: model,
            mcp_factory=lambda *_: FakeMcp([status]),
        )

    assert error.value.stage == "continuación tras MCP"
    assert error.value.request_count == 2
    assert status.called == 1


def test_agent_mcp_check_classifies_mcp_tool_execution_failure(tmp_path):
    model = SequenceModel(_responses(), tmp_path / "eval.jsonl")
    status = StatusTool(error=RuntimeError("MCP transport failure"))

    with pytest.raises(AgentMcpTestError) as error:
        check_agent_mcp(
            config(tmp_path),
            model_builder=lambda _: model,
            mcp_factory=lambda *_: FakeMcp([status]),
        )

    assert error.value.stage == "ejecución de MCP"
    assert status.called == 1
