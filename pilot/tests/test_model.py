from pathlib import Path
from types import SimpleNamespace

import pytest
from smolagents import Tool, ToolCallingAgent
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
    get_clean_message_list,
    tool_role_conversions,
)

from specnative_pilot import model
from specnative_pilot.config import Config
from specnative_pilot.secrets import ResolvedCredentials


def _config(reasoning_effort):
    return Config(
        repo=Path("."),
        model="groq-model",
        api_base="https://api.example.test/v1",
        api_key_env="OPENAI_API_KEY",
        question_mode="single",
        history=False,
        max_steps=12,
        mcp_python=None,
        mcp_script=None,
        reasoning_effort=reasoning_effort,
    )


def test_build_model_passes_configured_reasoning_effort(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(model, "resolve_credentials", lambda config: ResolvedCredentials("groq-model", "https://api.example.test/v1", "key"))
    monkeypatch.setattr(model, "OpenAIServerModel", fake_model)

    model.build_model(_config("low"))

    assert captured["reasoning_effort"] == "low"


def test_build_model_omits_reasoning_effort_when_unset(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(model, "resolve_credentials", lambda config: ResolvedCredentials("groq-model", None, "key"))
    monkeypatch.setattr(model, "OpenAIServerModel", fake_model)

    model.build_model(_config(None))

    assert "reasoning_effort" not in captured


def test_build_model_defaults_groq_gpt_oss_to_low(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        model,
        "resolve_credentials",
        lambda config: ResolvedCredentials("openai/gpt-oss-120b", "https://api.groq.com/openai/v1", "key"),
    )
    monkeypatch.setattr(model, "OpenAIServerModel", fake_model)

    model.build_model(_config(None))

    assert captured["reasoning_effort"] == "low"
    assert captured["tool_choice"] == "auto"


def test_build_model_leaves_tool_choice_default_for_other_providers(monkeypatch):
    captured = {}

    def fake_model(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        model,
        "resolve_credentials",
        lambda config: ResolvedCredentials("other-model", "https://api.example.test/v1", "key"),
    )
    monkeypatch.setattr(model, "OpenAIServerModel", fake_model)

    model.build_model(_config(None))

    assert "tool_choice" not in captured


def test_groq_gpt_oss_normalizes_direct_text_to_final_answer():
    message = ChatMessage(role=MessageRole.ASSISTANT, content="The MCP call succeeded.")

    result = _groq_model_instance().parse_tool_calls(message)

    assert result.tool_calls[0].function.name == "final_answer"
    assert result.tool_calls[0].function.arguments == {"answer": "The MCP call succeeded."}


def test_groq_gpt_oss_normalizes_json_pseudo_tool_only_for_final_answer_shape():
    message = ChatMessage(
        role=MessageRole.ASSISTANT,
        tool_calls=[
            ChatMessageToolCall(
                id="call-json",
                type="function",
                function=ChatMessageToolCallFunction(
                    name="json",
                    arguments='{"answer":"ASN_MCP_OK"}',
                ),
            )
        ],
    )

    result = _groq_model_instance().parse_tool_calls(message)

    assert result.tool_calls[0].function.name == "final_answer"
    assert result.tool_calls[0].function.arguments == {"answer": "ASN_MCP_OK"}


def test_other_providers_do_not_rewrite_json_tool_calls():
    instance = _groq_model_instance()
    instance.client_kwargs = {"base_url": "https://api.example.test/v1"}
    message = ChatMessage(
        role=MessageRole.ASSISTANT,
        tool_calls=[
            ChatMessageToolCall(
                id="call-json",
                type="function",
                function=ChatMessageToolCallFunction(name="json", arguments={"answer": "value"}),
            )
        ],
    )

    result = instance.parse_tool_calls(message)

    assert result.tool_calls[0].function.name == "json"


class _ProviderError(RuntimeError):
    status_code = 400


def _groq_model_instance():
    instance = object.__new__(model.OpenAIServerModel)
    instance.model_id = "openai/gpt-oss-120b"
    instance.client_kwargs = {"base_url": "https://api.groq.com/openai/v1"}
    instance.kwargs = {}
    instance.tool_name_key = "name"
    instance.tool_arguments_key = "arguments"
    instance.eval_log = _RequestCounter()
    return instance


class _RequestCounter:
    def __init__(self):
        self.request_count = 0

    def request_started(self):
        self.request_count += 1
        return self.request_count


def test_groq_gpt_oss_retries_matching_missing_tool_call_once(monkeypatch):
    requests = []

    def fake_generate(self, messages, **kwargs):
        serialized = get_clean_message_list(messages)
        requests.append((serialized, kwargs))
        self.eval_log.request_started()
        if len(requests) == 1:
            raise _ProviderError("400 Tool choice is required, but model did not call a tool")
        return ChatMessage(role=MessageRole.ASSISTANT, content="retried")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    user_messages = [ChatMessage(role=MessageRole.USER, content=[{"type": "text", "text": "describe an idea"}])]
    tool = SimpleNamespace(name="final_answer")

    result = _groq_model_instance().generate(user_messages, tools_to_call_from=[tool])

    assert result.content == "retried"
    assert len(requests) == 2
    assert len(requests[1][0]) == 1
    assert requests[1][0][0]["role"] == "user"
    assert requests[1][0][0]["content"][0]["text"] == "describe an idea"
    assert requests[1][0][0]["content"][1]["text"].startswith("La respuesta anterior")
    assert user_messages[0].content == [{"type": "text", "text": "describe an idea"}]
    assert requests[0][1] == requests[1][1]
    assert requests[1][1]["tools_to_call_from"] == [tool]


def _empty_completion(finish_reason="stop", reasoning="private reasoning"):
    return SimpleNamespace(
        content="",
        tool_calls=[],
        reasoning=reasoning,
        raw=SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason)]),
    )


def test_groq_gpt_oss_retries_empty_response_inside_the_same_agent_step(monkeypatch):
    requests = []
    responses = [
        _empty_completion(),
        _empty_completion(),
        ChatMessage(
            role=MessageRole.ASSISTANT,
            tool_calls=[
                ChatMessageToolCall(
                    id="call-status",
                    type="function",
                    function=ChatMessageToolCallFunction(name="status", arguments={}),
                )
            ],
        ),
        ChatMessage(
            role=MessageRole.ASSISTANT,
            tool_calls=[
                ChatMessageToolCall(
                    id="call-final",
                    type="function",
                    function=ChatMessageToolCallFunction(
                        name="final_answer", arguments={"answer": "ASN_MCP_OK"}
                    ),
                )
            ],
        ),
    ]
    sleep_calls = []

    def fake_generate(self, messages, **kwargs):
        requests.append((get_clean_message_list(messages), kwargs))
        self.eval_log.request_started()
        return responses.pop(0)

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    monkeypatch.setattr(model.time, "sleep", sleep_calls.append)
    instance = _groq_model_instance()
    instance.kwargs["reasoning_effort"] = "medium"

    class StatusTool(Tool):
        name = "status"
        description = "Return test status."
        inputs = {}
        output_type = "string"

        def __init__(self):
            self.is_initialized = True
            self.called = 0

        def forward(self):
            self.called += 1
            return "healthy"

    status = StatusTool()
    agent = ToolCallingAgent(
        tools=[status],
        model=instance,
        instructions="Call status once, then final_answer with ASN_MCP_OK.",
        max_steps=2,
        add_base_tools=False,
    )

    result = agent.run("Check MCP status and finish.")

    assert result == "ASN_MCP_OK"
    assert status.called == 1
    assert len([step for step in agent.memory.steps if hasattr(step, "step_number")]) == 2
    assert len(requests) == 4
    assert [delay for delay in sleep_calls] == [0.25, 0.5]
    assert requests[0][1]["max_completion_tokens"] == 1024
    assert all("La respuesta anterior llegó vacía" in str(request[0]) for request in requests[1:3])
    assert instance.kwargs["reasoning_effort"] == "medium"
    assert "private reasoning" not in repr(requests)


def test_groq_gpt_oss_grows_budget_only_for_length_and_caps_after_12_calls(monkeypatch):
    requests = []
    sleep_calls = []

    def fake_generate(self, messages, **kwargs):
        requests.append({**kwargs, "reasoning_effort": self.kwargs.get("reasoning_effort")})
        self.eval_log.request_started()
        return _empty_completion("length", "secret reasoning must not appear")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    monkeypatch.setattr(model.time, "sleep", sleep_calls.append)
    instance = _groq_model_instance()

    with pytest.raises(model.EmptyModelOutputError, match="en 12 intentos") as error:
        instance.generate(
            [ChatMessage(role=MessageRole.USER, content="Request")],
            tools_to_call_from=[SimpleNamespace(name="status")],
            tool_choice="auto",
        )

    assert len(requests) == 12
    assert [request["max_completion_tokens"] for request in requests] == [
        1024, 2048, 4096, 8192, 16384, 32768, 65536, 65536, 65536, 65536, 65536, 65536
    ]
    assert [request["reasoning_effort"] for request in requests] == [
        None, "low", "low", "low", "low", "low", "low", "low", "low", "low", "low", "low"
    ]
    assert len(sleep_calls) == 11
    assert sleep_calls == [0.25, 0.5, 1.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0]
    assert error.value.asn_tool_call_attempts == 12
    assert "finish_reason=length" in str(error.value)
    assert "secret reasoning" not in str(error.value)


def test_groq_gpt_oss_does_not_increase_budget_for_empty_stop_responses(monkeypatch):
    requests = []
    monkeypatch.setattr(model.time, "sleep", lambda _: None)

    def fake_generate(self, messages, **kwargs):
        requests.append(kwargs["max_completion_tokens"])
        self.eval_log.request_started()
        return _empty_completion("stop")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)

    with pytest.raises(model.EmptyModelOutputError):
        _groq_model_instance().generate(
            [ChatMessage(role=MessageRole.USER, content="Request")],
            tools_to_call_from=[SimpleNamespace(name="status")],
            tool_choice="auto",
        )

    assert requests == [1024] * 12


def test_groq_gpt_oss_retries_empty_response_without_tools(monkeypatch):
    requests = []
    empty = SimpleNamespace(content="", tool_calls=[])
    monkeypatch.setattr(model.time, "sleep", lambda _: None)

    def fake_generate(self, messages, **kwargs):
        requests.append(messages)
        return empty

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)

    with pytest.raises(model.EmptyModelOutputError):
        _groq_model_instance().generate([ChatMessage(role=MessageRole.USER, content="Request")])
    assert len(requests) == 12


def test_other_provider_retries_empty_response_within_same_step(monkeypatch):
    requests = []
    responses = [
        SimpleNamespace(content="", tool_calls=[], raw=SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop")])),
        ChatMessage(role=MessageRole.ASSISTANT, content="recovered"),
    ]
    monkeypatch.setattr(model.time, "sleep", lambda _: None)

    def fake_generate(self, messages, **kwargs):
        requests.append(messages)
        self.eval_log.request_started()
        return responses.pop(0)

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    instance = _groq_model_instance()
    instance.client_kwargs = {"base_url": "https://api.example.test/v1"}

    result = instance.generate(
        [ChatMessage(role=MessageRole.USER, content="Request")],
        tools_to_call_from=[SimpleNamespace(name="status")],
    )
    assert result.content == "recovered"
    assert len(requests) == 2


def test_empty_retry_falls_back_to_max_tokens_when_endpoint_rejects_new_parameter(monkeypatch):
    calls = []

    class UnsupportedParameter(RuntimeError):
        status_code = 400

    def fake_generate(self, messages, **kwargs):
        calls.append((dict(kwargs), self.kwargs.get("reasoning_effort")))
        self.eval_log.request_started()
        if len(calls) == 1:
            return _empty_completion()
        if "max_completion_tokens" in kwargs:
            raise UnsupportedParameter("Unsupported parameter: max_completion_tokens")
        return ChatMessage(role=MessageRole.ASSISTANT, content="recovered")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    monkeypatch.setattr(model.time, "sleep", lambda _: None)
    instance = _groq_model_instance()
    instance.client_kwargs = {"base_url": "https://api.other.test/v1"}

    result = instance.generate([ChatMessage(role=MessageRole.USER, content="Request")])

    assert result.content == "recovered"
    assert len(calls) == 3
    assert calls[1][0]["max_completion_tokens"] == 1024
    assert calls[2][0]["max_tokens"] == 1024
    assert calls[1][1] == calls[2][1] == "low"


def test_retry_after_tool_response_serializes_as_one_user_message():
    messages = [
        ChatMessage(
            role=MessageRole.TOOL_CALL,
            content=[{"type": "text", "text": "Calling status"}],
        ),
        ChatMessage(
            role=MessageRole.TOOL_RESPONSE,
            content=[{"type": "text", "text": "SpecNative status: healthy"}],
        ),
    ]

    retry_messages = model._append_retry_instruction(messages)
    serialized = get_clean_message_list(retry_messages, role_conversions=tool_role_conversions)

    assert [message["role"] for message in serialized] == ["assistant", "user"]
    assert len(serialized[1]["content"]) == 1
    assert serialized[1]["content"][0]["text"].startswith("SpecNative status: healthy")
    assert "La respuesta anterior no llamó ninguna herramienta" in serialized[1]["content"][0]["text"]
    assert messages[-1].content == [{"type": "text", "text": "SpecNative status: healthy"}]


def test_retry_normalizes_text_user_after_tool_response_before_role_merge():
    messages = [
        ChatMessage(
            role=MessageRole.TOOL_RESPONSE,
            content=[{"type": "text", "text": "MCP result"}],
        ),
        ChatMessage(role=MessageRole.USER, content="follow-up"),
    ]

    serialized = get_clean_message_list(
        model._append_retry_instruction(messages),
        role_conversions=tool_role_conversions,
    )

    assert len(serialized) == 1
    assert serialized[0]["role"] == "user"
    text = serialized[0]["content"][0]["text"]
    assert text.startswith("MCP result\nfollow-up")
    assert "La respuesta anterior no llamó ninguna herramienta" in text


def test_groq_gpt_oss_second_missing_tool_call_failure_is_marked_as_two_attempts(monkeypatch):
    def fake_generate(self, messages, **kwargs):
        get_clean_message_list(messages)
        self.eval_log.request_started()
        raise _ProviderError("400 Tool choice is required, but model did not call a tool")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)

    try:
        _groq_model_instance().generate([{"role": "user", "content": "idea"}], tools_to_call_from=[object()])
    except model.ToolCallRetryExhausted as error:
        assert model.tool_call_attempts(error) == 2
        assert "did not call a tool" in str(error)
    else:
        raise AssertionError("the second provider error should propagate")


def test_other_provider_errors_are_not_retried(monkeypatch):
    calls = []

    def fake_generate(self, messages, **kwargs):
        calls.append(messages)
        raise _ProviderError("400 invalid request")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)

    try:
        _groq_model_instance().generate([{"role": "user", "content": "idea"}], tools_to_call_from=[object()])
    except _ProviderError:
        pass
    else:
        raise AssertionError("the provider error should propagate")
    assert len(calls) == 1


def test_retry_format_error_does_not_count_as_a_provider_request(monkeypatch):
    instance = _groq_model_instance()
    calls = []

    def fake_generate(self, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            self.eval_log.request_started()
            raise _ProviderError("400 Tool choice is required, but model did not call a tool")
        raise AssertionError("wrong content: malformed local retry")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)

    try:
        instance.generate([{"role": "user", "content": "idea"}], tools_to_call_from=[object()])
    except model.ToolCallRetryExhausted as error:
        assert model.tool_call_attempts(error) == 1
        assert "malformed local retry" in str(error)
    else:
        raise AssertionError("the malformed retry should fail")


def test_matching_error_from_non_groq_endpoint_is_not_retried(monkeypatch):
    calls = []

    def fake_generate(self, messages, **kwargs):
        calls.append(messages)
        raise _ProviderError("400 Tool choice is required, but model did not call a tool")

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    instance = _groq_model_instance()
    instance.client_kwargs["base_url"] = "https://api.openai.com/v1"

    try:
        instance.generate([{"role": "user", "content": "idea"}], tools_to_call_from=[object()])
    except _ProviderError:
        pass
    else:
        raise AssertionError("the provider error should propagate")
    assert len(calls) == 1
