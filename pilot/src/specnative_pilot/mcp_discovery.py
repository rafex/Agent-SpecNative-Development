from __future__ import annotations

from pathlib import Path


MCP_RELATIVE_PATH = Path(".specnative") / "specnative_mcp.py"


def _ancestors(start: Path):
    current = start.resolve()
    if not current.is_dir():
        current = current.parent
    yield current
    yield from current.parents


def find_local_mcp(start: Path) -> Path | None:
    """Return the nearest project MCP while walking toward the filesystem root."""
    for directory in _ancestors(start):
        candidate = directory / MCP_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    return None


def resolve_project_repo(start: Path) -> Path:
    """Use the nearest MCP's project root when invoked from a subdirectory."""
    start = start.resolve()
    local = find_local_mcp(start)
    if local is not None:
        return local.parent.parent.resolve()
    return start if start.is_dir() else start.parent
