from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .controller import Controller
from .mcp_discovery import resolve_project_repo


def main(preflight_default: bool = False) -> int:
    parser = argparse.ArgumentParser(description="Piloto interactivo de definición SpecNative")
    parser.add_argument("command", nargs="?", choices=["setup"], help="Acción administrativa del proyecto")
    parser.add_argument("--repo", type=Path, help="Repositorio destino (por defecto, cwd o su proyecto SpecNative)")
    parser.add_argument("--clients", choices=["all", "codex", "claude", "opencode"], default="all")
    parser.add_argument("--initiative")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--question-mode", choices=["single", "batch"])
    parser.add_argument("--mcp-python", type=Path, help="Python que ejecuta el MCP externo")
    parser.add_argument("--mcp-script", type=Path, help="Script del MCP externo")
    parser.add_argument(
        "--preflight",
        action="store_true",
        default=preflight_default,
        help="Valida el contexto antes de iniciar el modelo",
    )
    args = parser.parse_args()
    if args.command == "setup":
        from .project_setup import setup_project

        repo = args.repo.resolve() if args.repo else Path.cwd()
        clients = {"codex", "claude", "opencode"} if args.clients == "all" else {args.clients}
        try:
            changed = setup_project(repo, clients)
        except (OSError, ValueError) as error:
            print(f"Error configurando ASN: {error}")
            return 2
        print(f"ASN configurado en {repo} para: {', '.join(sorted(clients))}.")
        if changed:
            print("Archivos creados o actualizados:")
            for path in changed:
                print(f"- {path.relative_to(repo)}")
        else:
            print("La configuración ya estaba actualizada.")
        return 0
    if (args.mcp_python is None) != (args.mcp_script is None):
        parser.error("--mcp-python y --mcp-script deben proporcionarse juntas")
    repo = args.repo.resolve() if args.repo else resolve_project_repo(Path.cwd())
    config = load_config(repo, args.config, args.question_mode, args.mcp_python, args.mcp_script)
    try:
        return Controller(config).run(args.initiative, preflight=args.preflight)
    except KeyboardInterrupt:
        print("\nSesión cancelada.")
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error del piloto: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


def asn_main() -> int:
    """Entry point público: ASN siempre valida el repositorio antes de iniciar."""
    return main(preflight_default=True)
