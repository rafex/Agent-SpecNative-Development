from pathlib import Path
from types import SimpleNamespace

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
        return "retried"

    monkeypatch.setattr(model._OpenAIServerModel, "generate", fake_generate)
    user_messages = [ChatMessage(role=MessageRole.USER, content=[{"type": "text", "text": "describe an idea"}])]
    tool = SimpleNamespace(name="final_answer")

    result = _groq_model_instance().generate(user_messages, tools_to_call_from=[tool])

    assert result == "retried"
    assert len(requests) == 2
    assert len(requests[1][0]) == 1
    assert requests[1][0][0]["role"] == "user"
    assert requests[1][0][0]["content"][0]["text"] == "describe an idea"
    assert requests[1][0][0]["content"][1]["text"].startswith("La respuesta anterior")
    assert user_messages[0].content == [{"type": "text", "text": "describe an idea"}]
    assert requests[0][1] == requests[1][1]
    assert requests[1][1]["tools_to_call_from"] == [tool]


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
