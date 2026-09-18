from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .mcp_discovery import find_local_mcp, resolve_project_repo


def main() -> int:
    parser = argparse.ArgumentParser(description="SpecNative MCP server launcher")
    parser.add_argument("--repo", type=Path)
    args, extra = parser.parse_known_args()
    repo = args.repo.resolve() if args.repo else resolve_project_repo(Path.cwd())
    local_script = find_local_mcp(repo)

    if local_script is not None:
        command = [sys.executable, str(local_script), "--repo", str(repo), *extra]
    else:
        command = [sys.executable, "-m", "specnative_pilot.mcp_server", "--repo", str(repo), *extra]
    os.execv(sys.executable, command)
    return 0
