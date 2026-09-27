from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

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
    def __init__(self, repo: Path, python: Path | None = None, script: Path | None = None) -> None:
        self.repo = repo
        self.python = python
        self.script = script
        self._client: MCPClient | None = None
        self._tools: dict[str, Any] = {}
        self._approval_client: MCPClient | None = None
        self._approval_tools: dict[str, Any] = {}
        self.approval_backend = "MCP del proyecto"

    def __enter__(self) -> "SpecNativeMcp":
        if (self.python is None) != (self.script is None):
            raise RuntimeError("--mcp-python y --mcp-script deben proporcionarse juntas")
        if self.python is None:
            command = sys.executable
            args = ["-m", "specnative_pilot.mcp_launcher", "--repo", str(self.repo)]
        else:
            command = str(self.python)
            args = [str(self.script), "--repo", str(self.repo)]
        params = StdioServerParameters(
            command=command,
            args=args,
            cwd=str(self.repo),
            env=dict(os.environ),
        )
        self._client = MCPClient(params, structured_output=True)
        tools = self._client.__enter__()
        self._tools = {tool.name: tool for tool in tools}
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._approval_client is not None:
            self._approval_client.__exit__(exc_type, exc_value, traceback)
            self._approval_client = None
        if self._client is not None:
            self._client.__exit__(exc_type, exc_value, traceback)

    @property
    def read_tools(self) -> list[Any]:
        return [tool for name, tool in self._tools.items() if name in READ_ONLY_TOOLS]

    def call(self, name: str, **arguments: Any) -> Any:
        return self._call_from(self._tools, name, **arguments)

    @staticmethod
    def _call_from(tools: dict[str, Any], name: str, **arguments: Any) -> Any:
        tool = tools.get(name)
        if tool is None:
            raise RuntimeError(f"MCP tool not available: {name}")
        result = tool.forward(**arguments)
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return result

    @contextmanager
    def approved_calls(self, required: set[str]) -> Iterator[Any]:
        """Expose write-capable MCP calls only inside an explicitly approved operation."""
        allowed = {"write_spec", "write_tasks", "apply_spec_template", "validate", "health_check"}
        if not required <= allowed:
            raise RuntimeError("Unsupported approved MCP operation")
        tools = self._tools
        if self.approval_backend_for(required) == "MCP incluido con ASN":
            if (self.python is None) != (self.script is None):
                raise RuntimeError("--mcp-python y --mcp-script deben proporcionarse juntas")
            if self._approval_client is None:
                params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "specnative_pilot.mcp_server", "--repo", str(self.repo)],
                    cwd=str(self.repo),
                    env=dict(os.environ),
                )
                client = MCPClient(params, structured_output=True)
                bundled_tools = client.__enter__()
                self._approval_client = client
                self._approval_tools = {tool.name: tool for tool in bundled_tools}
            tools = self._approval_tools
            if not required <= tools.keys():
                raise RuntimeError("El MCP incluido con ASN no ofrece todas las herramientas de aprobación requeridas")
            self.approval_backend = "MCP incluido con ASN"
        else:
            self.approval_backend = "MCP del proyecto"

        def call(name: str, **arguments: Any) -> Any:
            if name not in required:
                raise RuntimeError("La operación MCP no fue declarada para esta aprobación")
            return self._call_from(tools, name, **arguments)

        yield call

    def approval_backend_for(self, required: set[str]) -> str:
        return "MCP del proyecto" if required <= self._tools.keys() else "MCP incluido con ASN"
