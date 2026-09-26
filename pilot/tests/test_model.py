from pathlib import Path
from types import SimpleNamespace

from smolagents.models import ChatMessage, MessageRole, get_clean_message_list

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


class _ProviderError(RuntimeError):
    status_code = 400


def _groq_model_instance():
    instance = object.__new__(model.OpenAIServerModel)
    instance.model_id = "openai/gpt-oss-120b"
    instance.client_kwargs = {"base_url": "https://api.groq.com/openai/v1"}
    instance.kwargs = {}
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
