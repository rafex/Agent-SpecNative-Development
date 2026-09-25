from specnative_pilot import cli


def test_cli_reports_missing_model_and_auth_guidance(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("SPECNATIVE_AGENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
