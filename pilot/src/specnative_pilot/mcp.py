from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters
from smolagents import MCPClient


READ_ONLY_TOOLS = {
    "status", "validate", "list_specs", "list_tasks", "board", "read_spec",
    "read_context", "export_index", "resume", "context_snapshot", "health_check",
    "suggest_next", "read_template", "list_archetypes", "read_archetype",
    "list_decisions", "list_architecture", "list_conventions", "read_context_artifact",
    "list_templates",
}


class SpecNativeMcp:
    def __init__(self, repo: Path, python: Path, script: Path) -> None:
        self.repo = repo
        self.python = python
        self.script = script
        self._client: MCPClient | None = None
        self._tools: dict[str, Any] = {}

    def __enter__(self) -> "SpecNativeMcp":
        params = StdioServerParameters(
            command=str(self.python),
            args=[str(self.script), "--repo", str(self.repo)],
            cwd=str(self.repo),
            env=dict(os.environ),
        )
        self._client = MCPClient(params, structured_output=True)
        tools = self._client.__enter__()
        self._tools = {tool.name: tool for tool in tools}
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._client is not None:
            self._client.__exit__(exc_type, exc_value, traceback)

    @property
    def read_tools(self) -> list[Any]:
        return [tool for name, tool in self._tools.items() if name in READ_ONLY_TOOLS]

    def call(self, name: str, **arguments: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise RuntimeError(f"MCP tool not available: {name}")
        result = tool.forward(**arguments)
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return result
