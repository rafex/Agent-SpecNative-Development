import json
import os
from pathlib import Path

from specnative_pilot.failure_log import FailureLog, log_directory_candidates


def test_log_directory_candidates_follow_platform_fallbacks(tmp_path):
    linux = log_directory_candidates(
        platform="linux",
        home=tmp_path,
        environ={"XDG_STATE_HOME": str(tmp_path / "state")},
    )
    relative_xdg = log_directory_candidates(
        platform="linux",
        home=tmp_path,
        environ={"XDG_STATE_HOME": "relative-state"},
    )
    mac = log_directory_candidates(platform="darwin", home=tmp_path, environ={})

    assert linux == [Path("/var/log/asn"), tmp_path / "state/asn/logs", Path("/tmp/asn")]
    assert relative_xdg[1] == tmp_path / ".local/state/asn/logs"
    assert mac == [Path("/var/log/asn"), tmp_path / "Library/Logs/asn", Path("/tmp/asn")]


def test_failure_log_falls_back_to_user_directory_and_redacts_sensitive_values(tmp_path, capsys):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    fallback = tmp_path / "fallback"
    logger = FailureLog([blocker / "logs", fallback])
    token = "gsk_live_Secret123"

    try:
        raise RuntimeError(
            f"Authorization: Bearer {token}; api_key={token}; "
            "https://alice-secret:pass-secret@api.example.test/v1?token=private-value"
        )
    except RuntimeError as error:
        logger.record_failure(
            "provider_test",
            error,
            model="openai/gpt-oss-120b",
            endpoint="https://alice-secret:pass-secret@api.example.test/v1?token=private-value",
            api_key=token,
            include_traceback=True,
        )

    path = fallback / "asn-failures.jsonl"
    event = json.loads(path.read_text(encoding="utf-8"))
    rendered = path.read_text(encoding="utf-8")
    assert logger.path == path
    assert event["operation"] == "provider_test"
    assert event["endpoint"] == "https://api.example.test/v1?token=%5BOCULTO%5D"
    assert "Traceback" in event["traceback"]
    for secret in (token, "alice-secret:pass-secret@", "private-value"):
        assert secret not in rendered
    assert os.stat(fallback).st_mode & 0o777 == 0o700
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert capsys.readouterr().out == ""


def test_failure_log_rotates_with_configured_file_limit(tmp_path):
    logger = FailureLog([tmp_path / "logs"], max_bytes=400, backup_count=2)
    for index in range(8):
        try:
            raise RuntimeError(f"failure-{index}-" + ("x" * 180))
        except RuntimeError as error:
            logger.record_failure("agent_message", error)

    files = list((tmp_path / "logs").glob("asn-failures.jsonl*"))
    assert 1 < len(files) <= 3
    assert all(path.stat().st_size > 0 for path in files)
