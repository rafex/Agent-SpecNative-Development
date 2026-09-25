from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


DEFAULT_SOPS_FILE = Path(".specnative") / "agent.secrets.yaml"
DEFAULT_GOPASS_FILE = Path(".specnative") / "agent.gopass.toml"
GLOBAL_SOPS_FILE = Path("asn") / "agent.secrets.yaml"
AGE_IDENTITY_FILE = Path.home() / ".age" / "asn-key.txt"
SECRET_BACKENDS = {"auto", "none", "sops", "gopass"}


class SecretResolutionError(RuntimeError):
    """Raised when the selected secret provider cannot provide credentials."""


@dataclass(frozen=True)
class ResolvedCredentials:
    model: str
    api_base: str | None
    api_key: str | None


def _require_string(value: Any, name: str, source: str, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise SecretResolutionError(f"{source} no contiene {name}.")
        return None
    if not isinstance(value, str):
        raise SecretResolutionError(f"{source}: {name} debe ser texto.")
    if required and not value:
        raise SecretResolutionError(f"{source} contiene {name} vacío.")
    return value


def global_sops_file() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config").expanduser()
    return config_home / GLOBAL_SOPS_FILE


def _sops_environment() -> dict[str, str] | None:
    if not AGE_IDENTITY_FILE.is_file():
        return None
    return {**os.environ, "SOPS_AGE_KEY_FILE": str(AGE_IDENTITY_FILE)}


def _run_secret_command(
    command: list[str],
    *,
    cwd: Path,
    missing: str,
    failure: str,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    executable = shutil.which(command[0])
    if executable is None:
        raise SecretResolutionError(missing)
    command[0] = executable
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as error:
        raise SecretResolutionError(failure) from error
    if result.returncode != 0:
        raise SecretResolutionError(failure)
    return result.stdout


def _read_sops(path: Path, repo: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SecretResolutionError(f"No existe el archivo SOPS configurado: {path}")
    output = _run_secret_command(
        ["sops", "decrypt", "--input-type", "yaml", "--output-type", "json", str(path)],
        cwd=repo,
        missing="No se encontró `sops`; instala SOPS para usar el backend cifrado.",
        failure="SOPS no pudo descifrar el archivo de credenciales.",
        env=_sops_environment(),
    )
    try:
        import json

        value = json.loads(output)
    except (ValueError, TypeError) as error:
        raise SecretResolutionError("SOPS devolvió una configuración inválida.") from error
    if not isinstance(value, dict):
        raise SecretResolutionError("El archivo SOPS debe contener un objeto.")
    return value


def _read_gopass(path: Path, repo: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SecretResolutionError(f"No existe el archivo de referencias gopass: {path}")
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SecretResolutionError("El archivo de referencias gopass es inválido.") from error
    references = value.get("references")
    if not isinstance(references, dict):
        raise SecretResolutionError(f"{path}: falta la tabla [references].")
    resolved: dict[str, Any] = {}
    for name in ("model", "api_base", "api_key"):
        reference = references.get(name)
        if reference is None:
            continue
        if not isinstance(reference, str) or not reference.strip():
            raise SecretResolutionError(f"{path}: la referencia {name} es inválida.")
        output = _run_secret_command(
            ["gopass", "show", "--password-only", reference],
            cwd=repo,
            missing="No se encontró `gopass`; instala gopass para usar este backend.",
            failure=f"gopass no pudo leer la referencia {reference}.",
        )
        resolved[name] = output.rstrip("\r\n")
        if not resolved[name]:
            raise SecretResolutionError(f"La referencia gopass {reference} está vacía.")
    return resolved


def _provider_for(config: Config) -> str:
    backend = config.secrets_backend
    if backend not in SECRET_BACKENDS:
        raise SecretResolutionError(f"Backend de secretos inválido: {backend}.")
    if backend != "auto":
        return backend
    sops_file = config.secrets_file or config.repo / DEFAULT_SOPS_FILE
    gopass_file = config.gopass_file or config.repo / DEFAULT_GOPASS_FILE
    if sops_file.is_file():
        return "sops"
    if gopass_file.is_file():
        return "gopass"
    if global_sops_file().is_file():
        return "global_sops"
    return "none"


def resolve_credentials(config: Config) -> ResolvedCredentials:
    """Resolve model credentials without exposing secret values in diagnostics."""
    provider = _provider_for(config)
    sops_file = config.secrets_file or config.repo / DEFAULT_SOPS_FILE
    gopass_file = config.gopass_file or config.repo / DEFAULT_GOPASS_FILE
    values: dict[str, Any] = {}
    if provider == "sops":
        values = _read_sops(sops_file, config.repo)
    elif provider == "gopass":
        values = _read_gopass(gopass_file, config.repo)
    elif provider == "global_sops":
        values = _read_sops(global_sops_file(), config.repo)

    model = _require_string(values.get("model"), "model", provider) or config.model
    api_base = (
        _require_string(values.get("api_base"), "api_base", provider)
        or os.getenv("SPECNATIVE_AGENT_API_BASE")
        or config.api_base
    )
    if provider in {"sops", "gopass", "global_sops"}:
        api_key = _require_string(values.get("api_key"), "api_key", provider, required=True)
    else:
        api_key = os.getenv(config.api_key_env) or None
    return ResolvedCredentials(model=model or "", api_base=api_base or None, api_key=api_key)


def missing_credential_names(config: Config, credentials: ResolvedCredentials) -> list[str]:
    missing: list[str] = []
    if not credentials.model.strip():
        missing.append("SPECNATIVE_AGENT_MODEL")
    if not credentials.api_key or not credentials.api_key.strip():
        missing.append(config.api_key_env)
    return missing


def credential_setup_message(missing: list[str], api_key_env: str = "OPENAI_API_KEY") -> str:
    required = ", ".join(missing)
    return (
        f"Faltan credenciales ASN: {required}. Puedes exportarlas en el entorno del usuario/sistema "
        f"(SPECNATIVE_AGENT_MODEL y {api_key_env}; SPECNATIVE_AGENT_API_BASE es opcional), "
        "o ejecutar `asn --auth` para guardarlas cifradas con SOPS/age. "
        "Para credenciales de un proyecto usa `asn --auth --repo <ruta>`."
    )
