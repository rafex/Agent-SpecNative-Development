import json
import subprocess

import pytest

from specnative_pilot import provider_check
from specnative_pilot.secrets import ResolvedCredentials


def _credentials(api_base="https://api.example.test/openai/v1/"):
    return ResolvedCredentials(model="example-model", api_base=api_base, api_key="secret-token")


def test_provider_uses_configured_url_and_hides_token_from_argv(monkeypatch):
    captured = {}
    summaries = []

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["config"] = kwargs["input"]
        request = json.loads(args[args.index("--data-binary") + 1])
        captured["request"] = request
        return subprocess.CompletedProcess(
            args,
            0,
            stdout='{"choices":[{"message":{"content":"OK"}}]}\n200',
            stderr="",
        )

    monkeypatch.setattr(provider_check.shutil, "which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr(provider_check.subprocess, "run", fake_run)

    result = provider_check.check_provider(_credentials(), on_request=summaries.append)

    assert result.response == "OK"
    assert result.model == "example-model"
    assert "https://api.example.test/openai/v1/chat/completions" in captured["config"]
    assert captured["request"]["messages"] == [{"role": "user", "content": "Responde únicamente con OK."}]
    assert "secret-token" not in " ".join(captured["args"])
    assert "Bearer secret-token" in captured["config"]
    assert "POST https://api.example.test/openai/v1/chat/completions" in summaries[0]
    assert "Modelo: example-model" in summaries[0]
    assert "Authorization: Bearer secr…oken" in summaries[0]
    assert '"content": "Responde únicamente con OK."' in summaries[0]
    assert "secret-token" not in summaries[0]


def test_provider_reports_http_error_without_echoing_token(monkeypatch):
    summaries = []
    monkeypatch.setattr(provider_check.shutil, "which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr(
        provider_check.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            stdout='{"error":{"message":"bad secret-token"}}\n401',
            stderr="",
        ),
    )

    with pytest.raises(provider_check.ProviderTestError, match="HTTP 401") as error:
        provider_check.check_provider(_credentials(), on_request=summaries.append)
    assert "secret-token" not in str(error.value)
    assert summaries and "Petición de diagnóstico" in summaries[0]


def test_provider_reports_http_200_empty_text_with_metadata(monkeypatch):
    summaries = []
    monkeypatch.setattr(provider_check.shutil, "which", lambda name: "/usr/bin/curl")
    monkeypatch.setattr(
        provider_check.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            stdout='{"choices":[{"finish_reason":"length","message":{"content":null,"reasoning":"hidden"}}]}\n200',
            stderr="",
        ),
    )

    with pytest.raises(provider_check.ProviderTestError, match="HTTP 200.*finish_reason=length") as error:
        provider_check.check_provider(_credentials(), on_request=summaries.append)
    assert summaries and "POST https://api.example.test/openai/v1/chat/completions" in summaries[0]
    assert "reasoning" in str(error.value)
    assert "hidden" not in str(error.value)


def test_display_url_hides_userinfo_query_values_and_bare_query_tokens():
    display = provider_check._display_url(
        "https://alice:password@api.example.test/v1/chat/completions?api_key=secret-value&region=us&bare-token#fragment"
    )

    assert display.startswith("https://api.example.test/v1/chat/completions?")
    assert "api_key=%5BOCULTO%5D" in display
    assert "region=%5BOCULTO%5D" in display
    assert "%5BPARAMETRO_OCULTO%5D=%5BOCULTO%5D" in display
    for secret in ("alice", "password", "secret-value", "bare-token", "fragment"):
        assert secret not in display


def test_short_token_is_completely_hidden_in_request_summary():
    short_credentials = ResolvedCredentials(
        model="example-model",
        api_base="https://api.example.test/v1",
        api_key="shortkey",
    )

    summary = provider_check._prepare_request(short_credentials).summary

    assert "Authorization: Bearer [OCULTO]" in summary
    assert "shortkey" not in summary


def test_provider_request_uses_reasoning_effort_and_safe_completion_budget():
    request = provider_check._prepare_request(_credentials(), reasoning_effort="low")
    body = json.loads(request.body)

    assert body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] == 1024


def test_provider_request_omits_reasoning_effort_when_unset():
    request = provider_check._prepare_request(_credentials())
    body = json.loads(request.body)

    assert body["max_completion_tokens"] == 1024
    assert "reasoning_effort" not in body


def test_provider_reports_missing_curl(monkeypatch):
    monkeypatch.setattr(provider_check.shutil, "which", lambda name: None)

    with pytest.raises(provider_check.ProviderTestError, match="curl"):
        provider_check.check_provider(_credentials())


def test_provider_uses_openai_default_url_and_accepts_full_endpoint(monkeypatch):
    assert provider_check._chat_completions_url(None) == "https://api.openai.com/v1/chat/completions"
    assert provider_check._chat_completions_url("https://api.example.test/v1/chat/completions") == (
        "https://api.example.test/v1/chat/completions"
    )


def test_provider_rejects_invalid_base_url():
    with pytest.raises(provider_check.ProviderTestError, match="HTTP o HTTPS"):
        provider_check._chat_completions_url("file:///tmp/token")
