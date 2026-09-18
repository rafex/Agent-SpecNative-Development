from __future__ import annotations

import json
import os
import tempfile
import tomllib
from pathlib import Path
from typing import Iterable


CLIENTS = {"codex", "claude", "opencode"}
SKILL_PATHS = {
    "codex": Path(".codex/skills/specnative-agent/SKILL.md"),
    "claude": Path(".claude/skills/specnative-agent/SKILL.md"),
    "opencode": Path(".opencode/skills/specnative-agent/SKILL.md"),
}


def _skill_source() -> Path:
    return Path(__file__).parent / "resources" / "specnative-agent" / "SKILL.md"


def _server(name: str) -> dict[str, object]:
    return {"command": "asn-agent-mcp" if name == "asn-agent" else "asn-mcp", "args": ["--repo", "."]}


def _same_json_server(actual: object, expected: dict[str, object]) -> bool:
    return actual == expected


def _merge_claude(path: Path, text: str) -> str:
    data = json.loads(text) if text.strip() else {}
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{path}: mcpServers debe ser un objeto")
    for name in ("asn-agent", "specnative"):
        expected = _server(name)
        actual = servers.get(name)
        if actual is not None and (
            not isinstance(actual, dict)
            or actual.get("command") != expected["command"]
            or actual.get("args") != expected["args"]
        ):
            raise ValueError(f"{path}: el servidor {name} ya existe con otra configuración")
        servers.setdefault(name, expected)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _merge_opencode(path: Path, text: str) -> str:
    data = json.loads(text) if text.strip() else {"$schema": "https://opencode.ai/config.json"}
    mcp = data.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        raise ValueError(f"{path}: mcp debe ser un objeto")
    servers = mcp.setdefault("servers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"{path}: mcp.servers debe ser un objeto")
    for name in ("asn-agent", "specnative"):
        expected = {"type": "local", "command": [_server(name)["command"], "--repo", "."], "cwd": "."}
        actual = servers.get(name)
        if actual is not None and (
            not isinstance(actual, dict)
            or actual.get("type") != expected["type"]
            or actual.get("command") != expected["command"]
            or actual.get("cwd", ".") != expected["cwd"]
        ):
            raise ValueError(f"{path}: el servidor {name} ya existe con otra configuración")
        servers.setdefault(name, expected)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _codex_block(name: str) -> str:
    command = "asn-agent-mcp" if name == "asn-agent" else "asn-mcp"
    return (
        f"[mcp_servers.{name}]\n"
        f'command = "{command}"\n'
        'args = ["--repo", "."]\n'
        'cwd = "."\n'
        "startup_timeout_sec = 30\n"
        "tool_timeout_sec = 120\n"
        'default_tools_approval_mode = "writes"\n'
    )


def _merge_codex(path: Path, text: str) -> str:
    parsed = tomllib.loads(text) if text.strip() else {}
    configured = parsed.get("mcp_servers", {})
    if not isinstance(configured, dict):
        raise ValueError(f"{path}: mcp_servers debe ser una tabla")
    for name in ("asn-agent", "specnative"):
        actual = configured.get(name)
        expected_command = "asn-agent-mcp" if name == "asn-agent" else "asn-mcp"
        if actual is not None and (
            not isinstance(actual, dict)
            or actual.get("command") != expected_command
            or actual.get("args") != ["--repo", "."]
            or actual.get("cwd", ".") != "."
        ):
            raise ValueError(f"{path}: el servidor {name} ya existe con otra configuración")
    result = text.rstrip() + ("\n\n" if text.strip() else "")
    for name in ("asn-agent", "specnative"):
        marker = f"[mcp_servers.{name}]"
        if marker in text:
            continue
        result += _codex_block(name) + "\n"
    return result


def _existing(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _plan_file(updates: dict[Path, bytes], path: Path, content: str, replace_existing: bool = False) -> None:
    encoded = content.encode("utf-8")
    if path.exists() and not replace_existing and path.read_bytes() != encoded:
        raise ValueError(f"{path}: existe y no coincide con la integración ASN")
    if not path.exists() or path.read_bytes() != encoded:
        updates[path] = encoded


def _atomic_write(updates: dict[Path, bytes]) -> None:
    temporary: list[tuple[Path, Path]] = []
    try:
        for path, content in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            temporary.append((Path(name), path))
        for source, target in temporary:
            os.replace(source, target)
    finally:
        for source, _ in temporary:
            source.unlink(missing_ok=True)


def setup_project(repo: Path, clients: Iterable[str]) -> list[Path]:
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError(f"El proyecto no existe: {repo}")
    selected = set(clients)
    if not selected or not selected <= CLIENTS:
        raise ValueError(f"Clientes inválidos; usa: {', '.join(sorted(CLIENTS))}")
    skill = _skill_source().read_text(encoding="utf-8")
    updates: dict[Path, bytes] = {}
    for client in selected:
        _plan_file(updates, repo / SKILL_PATHS[client], skill)
    if "codex" in selected:
        path = repo / ".codex/config.toml"
        _plan_file(updates, path, _merge_codex(path, _existing(path)), replace_existing=True)
    if "claude" in selected:
        path = repo / ".mcp.json"
        _plan_file(updates, path, _merge_claude(path, _existing(path)), replace_existing=True)
    if "opencode" in selected:
        path = repo / "opencode.json"
        _plan_file(updates, path, _merge_opencode(path, _existing(path)), replace_existing=True)
    _atomic_write(updates)
    return sorted(updates)
