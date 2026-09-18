from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .controller import Controller


def main(preflight_default: bool = False) -> int:
    parser = argparse.ArgumentParser(description="Piloto interactivo de definición SpecNative")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
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
    repo = args.repo.resolve()
    config = load_config(repo, args.config, args.question_mode, args.mcp_python, args.mcp_script)
    try:
        return Controller(config).run(args.initiative, preflight=args.preflight)
    except KeyboardInterrupt:
        print("\nSesión cancelada.")
        return 130
    except (OSError, RuntimeError) as error:
        print(f"Error del piloto: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


def asn_main() -> int:
    """Entry point público: ASN siempre valida el repositorio antes de iniciar."""
    return main(preflight_default=True)
