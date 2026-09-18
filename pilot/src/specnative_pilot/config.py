from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    repo: Path
    model: str
    api_base: str | None
    api_key_env: str
    question_mode: str
    history: bool
    max_steps: int
    mcp_python: Path
    mcp_script: Path


def load_config(
    repo: Path,
    config_path: Path | None = None,
    question_mode: str | None = None,
    mcp_python: Path | None = None,
    mcp_script: Path | None = None,
) -> Config:
    raw: dict = {}
    path = config_path or repo / ".specnative" / "agent.toml"
    if path.exists():
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    agent = raw.get("agent", {})
    mcp = raw.get("mcp", {})
    python_path = Path(mcp_python or mcp.get("python", repo / ".specnative" / ".venv" / "bin" / "python"))
    script_path = Path(mcp_script or mcp.get("script", repo / ".specnative" / "specnative_mcp.py"))
    if not python_path.is_absolute():
        python_path = repo / python_path
    if not script_path.is_absolute():
        script_path = repo / script_path
    return Config(
        repo=repo,
        model=os.getenv("SPECNATIVE_AGENT_MODEL", agent.get("model", "")),
        api_base=os.getenv("SPECNATIVE_AGENT_API_BASE", agent.get("api_base")) or None,
        api_key_env=agent.get("api_key_env", "OPENAI_API_KEY"),
        question_mode=question_mode or os.getenv("SPECNATIVE_AGENT_QUESTION_MODE", agent.get("question_mode", "single")),
        history=os.getenv("SPECNATIVE_AGENT_HISTORY", str(agent.get("history", False))).lower() in {"1", "true", "yes", "on"},
        max_steps=int(agent.get("max_steps", 12)),
        mcp_python=python_path,
        mcp_script=script_path,
    )
