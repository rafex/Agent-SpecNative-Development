#!/usr/bin/env python3
"""Compatibility wrapper for projects that invoke the historical MCP path."""

import sys
from pathlib import Path


try:
    from specnative_pilot.mcp_server import main
except ModuleNotFoundError:
    # Keep direct execution useful from a source checkout before installation.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilot" / "src"))
    from specnative_pilot.mcp_server import main


if __name__ == "__main__":
    main()
