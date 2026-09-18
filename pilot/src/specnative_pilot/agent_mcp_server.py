from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .session import SessionError, SessionManager


def create_server(config: Any) -> FastMCP:
    manager = SessionManager(config)
    server = FastMCP(
        "asn-agent",
        instructions=(
            "ASN es el agente de definición SpecNative para el repositorio configurado. "
            "Usa agent_session_start antes de enviar mensajes. Las propuestas y "
            "plantillas requieren aprobación explícita mediante agent_session_approve."
        ),
    )

    @server.tool()
    def agent_session_start(initiative: str | None = None, question_mode: str | None = None) -> dict[str, Any]:
        """Valida el repositorio y abre una sesión del agente ASN."""
        return manager.start(initiative, question_mode)

    @server.tool()
    def agent_session_message(session_id: str, message: str) -> dict[str, Any]:
        """Envía un mensaje al agente sin aplicar propuestas pendientes."""
        try:
            return manager.get(session_id).message(message)
        except SessionError as error:
            return {"status": "error", "session_id": session_id, "text": str(error)}

    @server.tool()
    def agent_session_status(session_id: str) -> dict[str, Any]:
        """Consulta el estado y la aprobación pendiente de una sesión."""
        try:
            return manager.get(session_id).status()
        except SessionError as error:
            return {"status": "error", "session_id": session_id, "text": str(error)}

    @server.tool()
    def agent_session_approve(session_id: str, approval_token: str) -> dict[str, Any]:
        """Aprueba y aplica una propuesta o plantilla pendiente."""
        try:
            return manager.get(session_id).approve(approval_token)
        except (SessionError, OSError, ValueError, RuntimeError) as error:
            return {"status": "error", "session_id": session_id, "text": str(error)}

    @server.tool()
    def agent_session_reject(session_id: str, approval_token: str) -> dict[str, Any]:
        """Rechaza una propuesta o plantilla pendiente sin modificar archivos."""
        try:
            return manager.get(session_id).reject(approval_token)
        except SessionError as error:
            return {"status": "error", "session_id": session_id, "text": str(error)}

    @server.tool()
    def agent_session_close(session_id: str) -> dict[str, Any]:
        """Cierra una sesión y libera su conexión MCP interna."""
        try:
            return manager.close(session_id)
        except SessionError as error:
            return {"status": "error", "session_id": session_id, "text": str(error)}

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="ASN agent MCP server")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repositorio destino")
    parser.add_argument("--config", type=Path, help="Archivo .specnative/agent.toml alternativo")
    parser.add_argument("--mcp-python", type=Path, help="Python que ejecuta el MCP SpecNative externo")
    parser.add_argument("--mcp-script", type=Path, help="Script del MCP SpecNative externo")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if (args.mcp_python is None) != (args.mcp_script is None):
        parser.error("--mcp-python y --mcp-script deben proporcionarse juntas")
    repo = args.repo.resolve()
    config = load_config(repo, args.config, mcp_python=args.mcp_python, mcp_script=args.mcp_script)
    server = create_server(config)
    if args.transport == "sse":
        server.run(transport="sse", port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
