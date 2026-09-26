import pytest

from specnative_pilot import cli
from specnative_pilot.mcp_check import AgentMcpTestError, AgentMcpTestResult
from specnative_pilot.provider_check import ProviderTestError, ProviderTestResult
from specnative_pilot.secrets import ResolvedCredentials


def test_cli_version_exits_before_loading_config(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["asn", "--version"])
    monkeypatch.setattr(cli, "load_config", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no debe cargar configuración")))

    try:
        cli.main()
    except SystemExit as error:
        assert error.code == 0
    else:
        raise AssertionError("argparse debe salir tras mostrar la versión")

    output = capsys.readouterr().out.strip()
    assert output.startswith("asn ")
    assert cli.__version__ in output


def test_cli_reports_missing_model_and_auth_guidance(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("SPECNATIVE_AGENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "record_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("sys.argv", ["asn"])

    assert cli.main() == 2
    output = capsys.readouterr().out
    assert "SPECNATIVE_AGENT_MODEL" in output
    assert "OPENAI_API_KEY" in output
    assert "asn --auth" in output


def test_cli_auth_defaults_to_user_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["asn", "--auth"])
    called = {}

    def fake_auth(repo, **kwargs):
        called["repo"] = repo
        return [], False

    monkeypatch.setattr(cli, "authenticate", fake_auth)
    assert cli.main() == 0
    assert called["repo"] is None


def test_cli_auth_repo_option_selects_project_scope(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["asn", "--auth", "--repo", str(tmp_path)])
    called = {}

    def fake_auth(repo, **kwargs):
        called["repo"] = repo
        return [], False

    monkeypatch.setattr(cli, "authenticate", fake_auth)
    assert cli.main() == 0
    assert called["repo"] == tmp_path


def test_cli_test_checks_provider_without_starting_controller(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["asn", "--test", "--repo", str(tmp_path)])
    monkeypatch.setattr(cli, "resolve_project_repo", lambda path: tmp_path)
    credentials = ResolvedCredentials("openai/gpt-oss-120b", "https://api.groq.com/openai/v1", "key")
    monkeypatch.setattr(cli, "resolve_credentials", lambda config: credentials)
    monkeypatch.setattr(cli, "missing_credential_names", lambda config, credentials: [])
    monkeypatch.setenv("SPECNATIVE_AGENT_REASONING_EFFORT", "low")
    called = {}

    def fake_check(credentials, *, reasoning_effort, on_request):
        called["reasoning_effort"] = reasoning_effort
        on_request("Petición de diagnóstico")
        return ProviderTestResult("example-model", "OK", 200)

    monkeypatch.setattr(cli, "check_provider", fake_check)

    def fail_if_started(*args, **kwargs):
        raise AssertionError("--test no debe iniciar el agente")

    monkeypatch.setattr(cli, "Controller", fail_if_started)

    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "Petición de diagnóstico" in output
    assert "Proveedor validado" in output
    assert called["reasoning_effort"] == "low"


def test_cli_test_mcp_runs_full_agent_cycle_without_controller(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["asn", "--test-mcp", "--repo", str(tmp_path)])
    monkeypatch.setattr(cli, "resolve_project_repo", lambda path: tmp_path)
    credentials = ResolvedCredentials("mock-model", "https://provider.example/v1", "key")
    monkeypatch.setattr(cli, "resolve_credentials", lambda config: credentials)
    monkeypatch.setattr(cli, "missing_credential_names", lambda config, resolved: [])
    called = {}

    def fake_check(config):
        called["repo"] = config.repo
        return AgentMcpTestResult("mock-model", 245, 2, tmp_path / "eval.jsonl")

    monkeypatch.setattr(cli, "check_agent_mcp", fake_check)
    monkeypatch.setattr(cli, "Controller", lambda *_: (_ for _ in ()).throw(AssertionError("no interactive agent")))

    assert cli.main() == 0
    output = capsys.readouterr().out
    assert called["repo"] == tmp_path
    assert "continuó tras recibir la respuesta" in output
    assert "Peticiones al modelo: 2" in output
    assert str(tmp_path / "eval.jsonl") in output


def test_cli_test_mcp_reports_stage_and_records_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["asn", "--test-mcp", "--repo", str(tmp_path)])
    monkeypatch.setattr(cli, "resolve_project_repo", lambda path: tmp_path)
    credentials = ResolvedCredentials("mock-model", "https://provider.example/v1", "key")
    monkeypatch.setattr(cli, "resolve_credentials", lambda config: credentials)
    monkeypatch.setattr(cli, "missing_credential_names", lambda config, resolved: [])
    error = AgentMcpTestError("continuación tras MCP", "el agente no pudo continuar", request_count=2)
    monkeypatch.setattr(cli, "check_agent_mcp", lambda config: (_ for _ in ()).throw(error))
    logged = []
    monkeypatch.setattr(cli, "record_failure", lambda *args, **kwargs: logged.append((args, kwargs)))

    assert cli.main() == 2
    output = capsys.readouterr().out
    assert "continuación tras MCP" in output
    assert logged[0][0][0] == "agent_mcp_test"
    assert logged[0][1]["attempts"] == 2


def test_cli_rejects_combining_provider_and_mcp_tests(monkeypatch):
    monkeypatch.setattr("sys.argv", ["asn", "--test", "--test-mcp"])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


def test_cli_test_stops_before_curl_when_credentials_are_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["asn", "--test", "--repo", str(tmp_path)])
    monkeypatch.setattr(cli, "resolve_project_repo", lambda path: tmp_path)
    monkeypatch.setattr(cli, "resolve_credentials", lambda config: object())
    monkeypatch.setattr(cli, "missing_credential_names", lambda config, credentials: ["OPENAI_API_KEY"])
    monkeypatch.setattr(cli, "check_provider", lambda credentials: (_ for _ in ()).throw(AssertionError("curl no debe iniciar")))
    monkeypatch.setattr(cli, "record_failure", lambda *args, **kwargs: None)

    assert cli.main() == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().out


def test_cli_logs_provider_test_failure_with_resolved_model_and_key(tmp_path, monkeypatch, capsys):
    credentials = ResolvedCredentials("groq-model", "https://api.example.test/v1", "gsk_test_secret_value")
    logged = []
    monkeypatch.setattr("sys.argv", ["asn", "--test", "--repo", str(tmp_path)])
    monkeypatch.setattr(cli, "resolve_project_repo", lambda path: tmp_path)
    monkeypatch.setattr(cli, "resolve_credentials", lambda config: credentials)
    monkeypatch.setattr(cli, "missing_credential_names", lambda config, resolved: [])
    monkeypatch.setattr(cli, "check_provider", lambda *args, **kwargs: (_ for _ in ()).throw(ProviderTestError("HTTP 401")))
    monkeypatch.setattr(cli, "record_failure", lambda *args, **kwargs: logged.append((args, kwargs)))

    assert cli.main() == 2
    assert "HTTP 401" in capsys.readouterr().out
    assert logged[0][0][0] == "provider_test"
    assert logged[0][1]["model"] == "groq-model"
    assert logged[0][1]["api_key"] == credentials.api_key
