import hashlib
import json
import subprocess
from pathlib import Path

from specnative_pilot import mcp_provider


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


def release_responder(script: bytes):
    digest = hashlib.sha256(script).hexdigest()
    release = {
        "tag_name": "v-test",
        "assets": [
            {
                "name": "specnative_mcp.py",
                "browser_download_url": "https://example.test/specnative_mcp.py",
                "digest": f"sha256:{digest}",
            }
        ],
    }

    def respond(request, timeout):
        if request.full_url == mcp_provider.RELEASE_API_URL:
            return FakeResponse(json.dumps(release).encode())
        return FakeResponse(script)

    return respond


def test_release_is_downloaded_and_cached(tmp_path, monkeypatch):
    script = b"VALUE = 'release'\n"
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", release_responder(script))

    source = mcp_provider.resolve_remote_mcp()

    assert source is not None
    assert source.kind == "release"
    assert source.version == "v-test"
    assert source.path.read_bytes() == script
    metadata = json.loads((tmp_path / "cache" / "metadata.json").read_text())
    assert metadata["source"] == "release"
    assert metadata["digest"].startswith("sha256:")


def test_fresh_cache_avoids_network(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(cache))
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", release_responder(b"VALUE = 1\n"))
    first = mcp_provider.resolve_remote_mcp()

    def network_failure(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", network_failure)
    second = mcp_provider.resolve_remote_mcp()

    assert first is not None and second is not None
    assert second.path == first.path


def test_failed_refresh_uses_previous_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(cache))
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_TTL", "0")
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", release_responder(b"VALUE = 1\n"))
    first = mcp_provider.resolve_remote_mcp()

    def network_failure(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", network_failure)
    monkeypatch.setattr(mcp_provider.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no git")))
    second = mcp_provider.resolve_remote_mcp()

    assert first is not None and second is not None
    assert second.kind == "release"
    assert second.path.read_bytes() == b"VALUE = 1\n"


def test_invalid_release_digest_falls_back_to_repository(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(cache))
    invalid_release = {
        "tag_name": "v-invalid",
        "assets": [
            {
                "name": "specnative_mcp.py",
                "browser_download_url": "https://example.test/specnative_mcp.py",
                "digest": "sha256:wrong",
            }
        ],
    }
    responses = iter([FakeResponse(json.dumps(invalid_release).encode()), FakeResponse(b"VALUE = 2\n")])
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", lambda *args, **kwargs: next(responses))

    def fake_git(command, **kwargs):
        if command[:2] == ["git", "clone"]:
            checkout = Path(command[-1])
            source = checkout / mcp_provider.REPOSITORY_SCRIPT
            source.parent.mkdir(parents=True)
            source.write_bytes(b"VALUE = 3\n")
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "abc123\n", "")

    monkeypatch.setattr(mcp_provider.subprocess, "run", fake_git)
    source = mcp_provider.resolve_remote_mcp()

    assert source is not None
    assert source.kind == "repository"
    assert source.version == "abc123"
    assert source.path.read_bytes() == b"VALUE = 3\n"


def test_failed_release_and_repository_use_internal_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(mcp_provider.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no git")))

    assert mcp_provider.resolve_remote_mcp() is None


def test_never_mode_uses_cache_without_network(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(cache))
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", release_responder(b"VALUE = 4\n"))
    expected = mcp_provider.resolve_remote_mcp()
    monkeypatch.setenv("SPECNATIVE_MCP_UPDATE", "never")
    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network")))

    actual = mcp_provider.resolve_remote_mcp()

    assert expected is not None and actual is not None
    assert actual.path == expected.path


def test_force_mode_refreshes_fresh_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("SPECNATIVE_MCP_CACHE_DIR", str(cache))
    first_script = b"VALUE = 1\n"
    second_script = b"VALUE = 2\n"

    def release_metadata(tag, script):
        return json.dumps({
            "tag_name": tag,
            "assets": [{
                "name": "specnative_mcp.py",
                "browser_download_url": "https://example.test/specnative_mcp.py",
                "digest": f"sha256:{hashlib.sha256(script).hexdigest()}",
            }],
        }).encode()

    responses = iter([
        FakeResponse(release_metadata("v-one", first_script)),
        FakeResponse(first_script),
        FakeResponse(release_metadata("v-two", second_script)),
        FakeResponse(second_script),
    ])

    def respond(request, timeout):
        return next(responses)

    monkeypatch.setattr(mcp_provider.urllib.request, "urlopen", respond)
    first = mcp_provider.resolve_remote_mcp()
    monkeypatch.setenv("SPECNATIVE_MCP_UPDATE", "force")
    second = mcp_provider.resolve_remote_mcp()

    assert first is not None and second is not None
    assert second.path.read_bytes() == b"VALUE = 2\n"
