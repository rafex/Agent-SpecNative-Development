from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RELEASE_API_URL = "https://api.github.com/repos/rafex/SpecNative-Development/releases/latest"
REPOSITORY_URL = "https://github.com/rafex/SpecNative-Development.git"
RELEASE_ASSET = "specnative_mcp.py"
REPOSITORY_SCRIPT = Path("tools") / "specnative_mcp.py"
DEFAULT_TTL = 24 * 60 * 60


@dataclass(frozen=True)
class McpSource:
    kind: str
    path: Path
    version: str = ""
    digest: str = ""


def cache_directory() -> Path:
    configured = os.getenv("SPECNATIVE_MCP_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()
    xdg_cache = os.getenv("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "asn" / "mcp"
    return Path.home() / ".cache" / "asn" / "mcp"


def update_mode() -> str:
    mode = os.getenv("SPECNATIVE_MCP_UPDATE", "auto").lower()
    if mode not in {"auto", "never", "force"}:
        _log(f"valor SPECNATIVE_MCP_UPDATE inválido: {mode}; se usará auto")
        return "auto"
    return mode


def cache_ttl() -> int:
    value = os.getenv("SPECNATIVE_MCP_CACHE_TTL", str(DEFAULT_TTL))
    try:
        return max(0, int(value))
    except ValueError:
        _log(f"valor SPECNATIVE_MCP_CACHE_TTL inválido: {value}; se usará {DEFAULT_TTL}")
        return DEFAULT_TTL


def _log(message: str) -> None:
    print(f"asn-mcp: {message}", file=sys.stderr)


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _valid_python(content: bytes, filename: str) -> None:
    compile(content, filename, "exec")


def _metadata_path(directory: Path) -> Path:
    return directory / "metadata.json"


def _script_path(directory: Path) -> Path:
    return directory / RELEASE_ASSET


def _read_metadata(directory: Path) -> dict[str, Any] | None:
    try:
        with _metadata_path(directory).open(encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _cached_source(directory: Path) -> McpSource | None:
    metadata = _read_metadata(directory)
    path = _script_path(directory)
    if metadata is None or not path.is_file():
        return None
    try:
        content = path.read_bytes()
        _valid_python(content, str(path))
    except (OSError, SyntaxError):
        return None
    expected = str(metadata.get("digest", "")).removeprefix("sha256:")
    actual = _digest(content)
    if not expected or expected != actual:
        _log("la copia MCP cacheada no supera la verificación de integridad")
        return None
    return McpSource(
        kind=str(metadata.get("source", "cache")),
        path=path,
        version=str(metadata.get("version", "")),
        digest=actual,
    )


def _cache_is_fresh(directory: Path, now: float | None = None) -> bool:
    metadata = _read_metadata(directory)
    if metadata is None:
        return False
    try:
        return float(metadata["expires_at"]) > (time.time() if now is None else now)
    except (KeyError, TypeError, ValueError):
        return False


def _write_cache(directory: Path, content: bytes, source: str, version: str, ttl: int) -> McpSource:
    _valid_python(content, RELEASE_ASSET)
    digest = _digest(content)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, prefix="mcp-", suffix=".py", delete=False) as handle:
        temporary_script = Path(handle.name)
        handle.write(content)
    try:
        os.replace(temporary_script, _script_path(directory))
        metadata = {
            "source": source,
            "version": version,
            "digest": f"sha256:{digest}",
            "fetched_at": time.time(),
            "expires_at": time.time() + ttl,
        }
        with tempfile.NamedTemporaryFile(
            dir=directory, prefix="metadata-", suffix=".json", mode="w", encoding="utf-8", delete=False
        ) as handle:
            temporary_metadata = Path(handle.name)
            json.dump(metadata, handle, indent=2)
            handle.write("\n")
        os.replace(temporary_metadata, _metadata_path(directory))
    finally:
        temporary_script.unlink(missing_ok=True)
        if "temporary_metadata" in locals():
            temporary_metadata.unlink(missing_ok=True)
    return McpSource(kind=source, path=_script_path(directory), version=version, digest=digest)


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "asn-mcp-updater",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("respuesta de releases inválida")
    return value


def _fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "asn-mcp-updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _download_release(directory: Path, ttl: int) -> McpSource:
    release = _fetch_json(RELEASE_API_URL)
    tag = str(release.get("tag_name", ""))
    assets = release.get("assets", [])
    asset = next((item for item in assets if item.get("name") == RELEASE_ASSET), None)
    if not isinstance(asset, dict):
        raise RuntimeError(f"el release {tag or 'latest'} no contiene {RELEASE_ASSET}")
    url = asset.get("browser_download_url")
    declared_digest = str(asset.get("digest", ""))
    if not url or not declared_digest.startswith("sha256:"):
        raise RuntimeError("el asset MCP no tiene URL o digest SHA-256 verificable")
    content = _fetch_bytes(str(url))
    actual = _digest(content)
    if actual != declared_digest.removeprefix("sha256:"):
        raise RuntimeError("el digest del asset MCP no coincide con GitHub")
    return _write_cache(directory, content, "release", tag, ttl)


def _clone_repository(directory: Path, ttl: int) -> McpSource:
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="asn-mcp-repository-", dir=directory.parent) as temporary:
        checkout = Path(temporary) / "source"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "main", REPOSITORY_URL, str(checkout)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        source = checkout / REPOSITORY_SCRIPT
        if not source.is_file():
            raise RuntimeError(f"el repositorio no contiene {REPOSITORY_SCRIPT}")
        content = source.read_bytes()
        version = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        return _write_cache(directory, content, "repository", version, ttl)


def resolve_remote_mcp() -> McpSource | None:
    """Resolve a downloaded MCP, returning None for the packaged fallback."""
    directory = cache_directory()
    cached = _cached_source(directory)
    mode = update_mode()

    if mode == "never":
        if cached is not None:
            _log(f"usando MCP cacheado ({cached.version or 'sin versión'})")
        return cached
    if mode == "auto" and cached is not None and _cache_is_fresh(directory):
        return cached

    failures: list[str] = []
    try:
        source = _download_release(directory, cache_ttl())
        _log(f"MCP actualizado desde release {source.version}")
        return source
    except Exception as error:  # network, GitHub response, or validation failures
        failures.append(f"release: {error}")
    try:
        source = _clone_repository(directory, cache_ttl())
        _log(f"MCP actualizado desde repositorio ({source.version})")
        return source
    except Exception as error:  # git unavailable, network, or validation failures
        failures.append(f"repositorio: {error}")

    if cached is not None:
        _log("no se pudo actualizar el MCP; usando la última copia cacheada")
        return cached
    _log("no se pudo actualizar el MCP; usando la versión interna")
    for failure in failures:
        _log(failure)
    return None
