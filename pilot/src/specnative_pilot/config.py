from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .mcp_discovery import find_local_mcp
from .secrets import DEFAULT_GOPASS_FILE, DEFAULT_SOPS_FILE, SECRET_BACKENDS


@dataclass(frozen=True)
class Config:
    repo: Path
    model: str
    api_base: str | None
    api_key_env: str
    question_mode: str
    history: bool
    max_steps: int
    mcp_python: Path | None
    mcp_script: Path | None
    reasoning_effort: str | None = None
    secrets_backend: str = "auto"
    secrets_file: Path | None = None
    gopass_file: Path | None = None


def load_config(
    repo: Path,
    config_path: Path | None = None,
    question_mode: str | None = None,
    mcp_python: Path | None = None,
    mcp_script: Path | None = None,
    secrets_backend: str | None = None,
    secrets_file: Path | None = None,
    gopass_file: Path | None = None,
) -> Config:
    raw: dict = {}
    path = config_path or repo / ".specnative" / "agent.toml"
    if path.exists():
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    agent = raw.get("agent", {})
    mcp = raw.get("mcp", {})
    secrets = raw.get("secrets", {})
    if not isinstance(secrets, dict):
        raise ValueError("[secrets] debe ser una tabla")
    configured_mcp = find_local_mcp(repo) is None
    python_value = mcp_python if mcp_python is not None else (mcp.get("python") if configured_mcp else None)
    script_value = mcp_script if mcp_script is not None else (mcp.get("script") if configured_mcp else None)
    if (python_value is None) != (script_value is None):
        raise ValueError("la configuración MCP debe incluir python y script juntos")
    python_path = Path(python_value) if python_value else None
    script_path = Path(script_value) if script_value else None
    if python_path is not None and not python_path.is_absolute():
        python_path = repo / python_path
    if script_path is not None and not script_path.is_absolute():
        script_path = repo / script_path
    backend = secrets_backend if secrets_backend is not None else secrets.get("backend", "auto")
    if backend not in SECRET_BACKENDS:
        raise ValueError(f"Backend de secretos inválido: {backend}")

    def resolve_path(value: Path | str | None, default: Path) -> Path:
        path_value = value if value is not None else default
        path = Path(path_value)
        return path if path.is_absolute() else repo / path

    resolved_secrets_file = resolve_path(
        secrets_file if secrets_file is not None else secrets.get("file"),
        DEFAULT_SOPS_FILE,
    )
    resolved_gopass_file = resolve_path(
        gopass_file if gopass_file is not None else secrets.get("gopass_file"),
        DEFAULT_GOPASS_FILE,
    )
    reasoning_effort = os.getenv("SPECNATIVE_AGENT_REASONING_EFFORT") or agent.get("reasoning_effort") or None
    if reasoning_effort is not None:
        if not isinstance(reasoning_effort, str):
            raise ValueError("[agent].reasoning_effort debe ser texto")
        reasoning_effort = reasoning_effort.strip() or None
    return Config(
        repo=repo,
        model=os.getenv("SPECNATIVE_AGENT_MODEL", agent.get("model", "")),
        api_base=os.getenv("SPECNATIVE_AGENT_API_BASE", agent.get("api_base")) or None,
        reasoning_effort=reasoning_effort,
        api_key_env=agent.get("api_key_env", "OPENAI_API_KEY"),
        question_mode=question_mode or os.getenv("SPECNATIVE_AGENT_QUESTION_MODE", agent.get("question_mode", "single")),
        history=os.getenv("SPECNATIVE_AGENT_HISTORY", str(agent.get("history", False))).lower() in {"1", "true", "yes", "on"},
        max_steps=int(agent.get("max_steps", 12)),
        mcp_python=python_path,
        mcp_script=script_path,
        secrets_backend=backend,
        secrets_file=resolved_secrets_file,
        gopass_file=resolved_gopass_file,
    )
