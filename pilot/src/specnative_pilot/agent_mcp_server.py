from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .failure_log import record_failure
from .session import SessionError, SessionManager


def _record_tool_failure(
    operation: str,
    error: BaseException,
    manager: SessionManager,
    *,
    session_id: str | None = None,
    traceback_required: bool = False,
) -> None:
    config = manager.config
    session = getattr(manager, "sessions", {}).get(session_id) if session_id else None
    model_object = getattr(getattr(session, "agent", None), "model", None)
    client_kwargs = getattr(model_object, "client_kwargs", {}) or {}
    record_failure(
        operation,
        error,
        model=getattr(model_object, "model_id", None) or config.model,
        endpoint=client_kwargs.get("base_url") or config.api_base,
        api_key=client_kwargs.get("api_key"),
        include_traceback=traceback_required,
    )


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
            _record_tool_failure("agent_mcp_message", error, manager, session_id=session_id)
            return {"status": "error", "session_id": session_id, "text": str(error)}
        except Exception as error:
            _record_tool_failure("agent_mcp_message", error, manager, session_id=session_id, traceback_required=True)
            raise

    @server.tool()
    def agent_session_status(session_id: str) -> dict[str, Any]:
        """Consulta el estado y la aprobación pendiente de una sesión."""
        try:
            return manager.get(session_id).status()
        except SessionError as error:
            _record_tool_failure("agent_mcp_status", error, manager, session_id=session_id)
            return {"status": "error", "session_id": session_id, "text": str(error)}
        except Exception as error:
            _record_tool_failure("agent_mcp_status", error, manager, session_id=session_id, traceback_required=True)
            raise

    @server.tool()
    def agent_session_approve(session_id: str, approval_token: str) -> dict[str, Any]:
        """Aprueba y aplica una propuesta o plantilla pendiente."""
        try:
            return manager.get(session_id).approve(approval_token)
        except (SessionError, OSError, ValueError, RuntimeError) as error:
            _record_tool_failure(
                "agent_mcp_approve",
                error,
                manager,
                session_id=session_id,
                traceback_required=not isinstance(error, SessionError),
            )
            return {"status": "error", "session_id": session_id, "text": str(error)}
        except Exception as error:
            _record_tool_failure("agent_mcp_approve", error, manager, session_id=session_id, traceback_required=True)
            raise

    @server.tool()
    def agent_session_reject(session_id: str, approval_token: str) -> dict[str, Any]:
        """Rechaza una propuesta o plantilla pendiente sin modificar archivos."""
        try:
            return manager.get(session_id).reject(approval_token)
        except SessionError as error:
            _record_tool_failure("agent_mcp_reject", error, manager, session_id=session_id)
            return {"status": "error", "session_id": session_id, "text": str(error)}
        except Exception as error:
            _record_tool_failure("agent_mcp_reject", error, manager, session_id=session_id, traceback_required=True)
            raise

    @server.tool()
    def agent_session_close(session_id: str) -> dict[str, Any]:
        """Cierra una sesión y libera su conexión MCP interna."""
        try:
            return manager.close(session_id)
        except SessionError as error:
            _record_tool_failure("agent_mcp_close", error, manager, session_id=session_id)
            return {"status": "error", "session_id": session_id, "text": str(error)}
        except Exception as error:
            _record_tool_failure("agent_mcp_close", error, manager, session_id=session_id, traceback_required=True)
            raise

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="ASN agent MCP server")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repositorio destino")
    parser.add_argument("--config", type=Path, help="Archivo .specnative/agent.toml alternativo")
    parser.add_argument("--mcp-python", type=Path, help="Python que ejecuta el MCP SpecNative externo")
    parser.add_argument("--mcp-script", type=Path, help="Script del MCP SpecNative externo")
    parser.add_argument("--secrets-backend", choices=["auto", "none", "sops", "gopass"])
    parser.add_argument("--secrets-file", type=Path, help="Archivo SOPS de credenciales")
    parser.add_argument("--gopass-file", type=Path, help="Archivo de referencias gopass")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if (args.mcp_python is None) != (args.mcp_script is None):
        parser.error("--mcp-python y --mcp-script deben proporcionarse juntas")
    repo = args.repo.resolve()
    config = None
    try:
        config = load_config(
            repo,
            args.config,
            mcp_python=args.mcp_python,
            mcp_script=args.mcp_script,
            secrets_backend=args.secrets_backend,
            secrets_file=args.secrets_file,
            gopass_file=args.gopass_file,
        )
        server = create_server(config)
        if args.transport == "sse":
            server.run(transport="sse", port=args.port)
        else:
            server.run(transport="stdio")
    except Exception as error:
        record_failure(
            "agent_mcp_server",
            error,
            model=config.model if config else os.getenv("SPECNATIVE_AGENT_MODEL"),
            endpoint=config.api_base if config else os.getenv("SPECNATIVE_AGENT_API_BASE"),
            include_traceback=True,
        )
        raise


if __name__ == "__main__":
    main()
