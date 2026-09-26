from __future__ import annotations

import argparse
from pathlib import Path

from .config import effective_reasoning_effort, load_config
from .controller import Controller
from .failure_log import record_failure
from . import __version__
from .mcp_discovery import resolve_project_repo
from .provider_check import ProviderTestError, check_provider
from .secret_setup import SecretSetupError, authenticate, initialize_secrets
from .secrets import SecretResolutionError, credential_setup_message, missing_credential_names, resolve_credentials


def main(preflight_default: bool = False) -> int:
    parser = argparse.ArgumentParser(description="Piloto interactivo de definición SpecNative")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("command", nargs="?", choices=["setup", "secrets"], help="Acción administrativa del proyecto")
    parser.add_argument("subcommand", nargs="?", choices=["init"], help="Subcomando administrativo")
    parser.add_argument("--repo", type=Path, help="Repositorio destino (por defecto, cwd o su proyecto SpecNative)")
    parser.add_argument("--auth", action="store_true", help="Configura credenciales ASN cifradas con SOPS/age")
    parser.add_argument("--test", action="store_true", help="Valida URL, modelo y token con una petición corta vía curl")
    parser.add_argument("--clients", choices=["all", "codex", "claude", "opencode"], default="all")
    parser.add_argument("--backend", choices=["sops", "gopass"], help="Backend para `asn secrets init`")
    parser.add_argument("--prefix", help="Prefijo de referencias para gopass")
    parser.add_argument("--initiative")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--question-mode", choices=["single", "batch"])
    parser.add_argument("--mcp-python", type=Path, help="Python que ejecuta el MCP externo")
    parser.add_argument("--mcp-script", type=Path, help="Script del MCP externo")
    parser.add_argument("--secrets-backend", choices=["auto", "none", "sops", "gopass"])
    parser.add_argument("--secrets-file", type=Path, help="Archivo SOPS de credenciales")
    parser.add_argument("--gopass-file", type=Path, help="Archivo de referencias gopass")
    parser.add_argument(
        "--preflight",
        action="store_true",
        default=preflight_default,
        help="Valida el contexto antes de iniciar el modelo",
    )
    args = parser.parse_args()
    if args.test and (args.command is not None or args.subcommand is not None or args.auth):
        parser.error("`--test` no se combina con comandos administrativos ni `--auth`")
    if args.auth:
        if args.command is not None or args.subcommand is not None:
            parser.error("`--auth` no se combina con otro comando")
        try:
            changed, cancelled = authenticate(
                args.repo,
                confirm_replace=lambda prompt: input(f"{prompt} [s/N] ").strip().lower() in {"s", "si", "sí", "y", "yes"},
            )
        except KeyboardInterrupt:
            print("\nAutenticación cancelada.")
            return 0
        except (OSError, SecretSetupError, ValueError) as error:
            print(f"Error configurando autenticación ASN: {error}")
            return 2
        if cancelled:
            print("Autenticación cancelada; no se modificó ningún archivo.")
            return 0
        scope = f"el proyecto {args.repo.resolve()}" if args.repo else "tu usuario"
        print(f"Credenciales ASN cifradas para {scope}.")
        for path in changed:
            print(f"- {path}")
        return 0
    if args.command == "secrets":
        if args.subcommand != "init":
            parser.error("usa `asn secrets init --backend sops|gopass`")
        if args.backend is None:
            parser.error("`asn secrets init` requiere --backend sops o --backend gopass")
        repo = args.repo.resolve() if args.repo else Path.cwd()
        try:
            changed, instructions = initialize_secrets(
                repo,
                args.backend,
                secrets_file=args.secrets_file,
                gopass_file=args.gopass_file,
                prefix=args.prefix,
            )
        except (OSError, SecretSetupError, ValueError) as error:
            print(f"Error configurando secretos ASN: {error}")
            return 2
        print(f"Backend de secretos `{args.backend}` configurado en {repo}.")
        for path in changed:
            print(f"- {path.relative_to(repo)}")
        if instructions:
            print("\nRegistra las referencias gopass con:")
            for instruction in instructions:
                print(f"  {instruction}")
        return 0
    if args.subcommand is not None:
        parser.error("el subcomando sólo es válido para `asn secrets init`")
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
    config = load_config(
        repo,
        args.config,
        args.question_mode,
        args.mcp_python,
        args.mcp_script,
        args.secrets_backend,
        args.secrets_file,
        args.gopass_file,
    )
    try:
        credentials = resolve_credentials(config)
        missing = missing_credential_names(config, credentials)
        if missing:
            message = credential_setup_message(missing, config.api_key_env)
            record_failure("credentials", RuntimeError(message), model=config.model, endpoint=config.api_base)
            print(message)
            return 2
    except SecretResolutionError as error:
        record_failure("credentials", error, model=config.model, endpoint=config.api_base)
        print(f"No se pudieron resolver las credenciales ASN: {error}")
        print("Revisa el backend configurado o ejecuta `asn --auth` para configurarlo.")
        return 2
    if args.test:
        try:
            result = check_provider(
                credentials,
                reasoning_effort=effective_reasoning_effort(
                    config,
                    model=credentials.model,
                    api_base=credentials.api_base,
                ),
                on_request=lambda summary: print(summary),
            )
        except ProviderTestError as error:
            record_failure(
                "provider_test",
                error,
                model=credentials.model,
                endpoint=credentials.api_base,
                api_key=credentials.api_key,
            )
            print(f"Falló la validación del proveedor: {error}")
            return 2
        print(f"Proveedor validado: modelo `{result.model}`, HTTP {result.status_code}, respuesta: {result.response}")
        return 0
    try:
        return Controller(config).run(args.initiative, preflight=args.preflight)
    except KeyboardInterrupt:
        print("\nSesión cancelada.")
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        record_failure(
            "asn_cli",
            error,
            model=credentials.model,
            endpoint=credentials.api_base,
            api_key=credentials.api_key,
            reasoning_effort=effective_reasoning_effort(
                config,
                model=credentials.model,
                api_base=credentials.api_base,
            ),
            include_traceback=True,
        )
        print(f"Error del piloto: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


def asn_main() -> int:
    """Entry point público: ASN siempre valida el repositorio antes de iniciar."""
    return main(preflight_default=True)
