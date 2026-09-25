from __future__ import annotations

import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .secrets import AGE_IDENTITY_FILE, DEFAULT_GOPASS_FILE, DEFAULT_SOPS_FILE, global_sops_file


class SecretSetupError(RuntimeError):
    """Raised when secret backend initialization cannot complete safely."""


class SecretToolsMissingError(SecretSetupError):
    """Raised with installation guidance when SOPS/age tools are unavailable."""


def _install_guidance(missing: list[str]) -> str:
    system = platform.system().lower()
    if system == "darwin":
        command = "brew install sops age"
    elif system == "linux":
        distro = ""
        try:
            for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
                if line.startswith("ID="):
                    distro = line.partition("=")[2].strip().strip('"').lower()
                    break
        except OSError:
            pass
        if distro in {"debian", "ubuntu", "linuxmint", "pop"}:
            command = "sudo apt install age sops"
        elif distro in {"fedora", "rhel", "centos"}:
            command = "sudo dnf install age sops"
        elif distro in {"arch", "manjaro", "endeavouros"}:
            command = "sudo pacman -S age sops"
        else:
            command = "Instala `sops` y `age` con el gestor de paquetes de tu distribución."
    elif system == "windows":
        command = "Instala SOPS y age con el gestor de paquetes disponible, por ejemplo Scoop o Chocolatey."
    else:
        command = "Instala `sops` y `age` desde sus instrucciones oficiales para tu sistema."
    names = ", ".join(f"`{name}`" for name in missing)
    return f"Faltan {names}. Instálalos y vuelve a ejecutar `asn --auth`.\n{command}"


def _require_auth_tools() -> dict[str, str]:
    missing = [name for name in ("sops", "age", "age-keygen") if shutil.which(name) is None]
    if missing:
        raise SecretToolsMissingError(_install_guidance(missing))
    return {name: shutil.which(name) or name for name in ("sops", "age", "age-keygen")}


def _run_auth_command(
    command: list[str],
    *,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
):
    try:
        result = subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=str(cwd) if cwd is not None else None,
        )
    except OSError as error:
        raise SecretSetupError(f"No se pudo ejecutar `{Path(command[0]).name}`.") from error
    if result.returncode != 0:
        raise SecretSetupError(f"`{Path(command[0]).name}` falló; revisa la configuración de SOPS/age.")
    return result.stdout


def _age_identity(tools: dict[str, str]) -> tuple[Path, str]:
    identity = AGE_IDENTITY_FILE
    identity.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(identity.parent, 0o700)
    if not identity.exists():
        _run_auth_command([tools["age-keygen"], "-o", str(identity)])
        os.chmod(identity, 0o600)
    if not identity.is_file():
        raise SecretSetupError(f"La identidad age no es un archivo regular: {identity}")
    os.chmod(identity, 0o600)
    recipient = _run_auth_command([tools["age-keygen"], "-y", str(identity)]).strip()
    if not recipient.startswith("age1"):
        raise SecretSetupError("age-keygen no devolvió un recipient age válido.")
    return identity, recipient


def _encrypt_sops(
    payload: str,
    target: Path,
    *,
    sops_command: str,
    recipient: str | None = None,
    identity: Path | None = None,
    cwd: Path | None = None,
) -> str:
    command = [sops_command, "encrypt", "--input-type", "json", "--output-type", "yaml"]
    if recipient:
        command.extend(("--age", recipient))
    command.extend(("--filename-override", str(target)))
    temporary_input: Path | None = None
    input_text: str | None = payload
    if os.name == "posix":
        input_path = "/dev/stdin"
    else:
        fd, name = tempfile.mkstemp(prefix="asn-auth-")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        temporary_input = Path(name)
        input_path = str(temporary_input)
        input_text = None
    command.append(input_path)
    env = {**os.environ, "SOPS_AGE_KEY_FILE": str(identity)} if identity else None
    try:
        return _run_auth_command(command, input_text=input_text, env=env, cwd=cwd)
    finally:
        if temporary_input is not None:
            temporary_input.unlink(missing_ok=True)


def _require_command(name: str) -> str:
    command = shutil.which(name)
    if command is None:
        raise SecretSetupError(f"No se encontró `{name}` en PATH.")
    return command


def _slug(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return result or "project"


def _relative(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _agent_config(repo: Path, backend: str, target: Path, *, replace_existing: bool = False) -> tuple[Path, bytes]:
    path = repo / ".specnative" / "agent.toml"
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if original.strip():
        import tomllib

        try:
            parsed = tomllib.loads(original)
        except tomllib.TOMLDecodeError as error:
            raise SecretSetupError(f"{path}: TOML inválido; no se modificó el proyecto.") from error
        existing = parsed.get("secrets")
        if existing is not None:
            expected_key = "file" if backend == "sops" else "gopass_file"
            expected = {"backend": backend, expected_key: _relative(target, repo)}
            if all(existing.get(key) == value for key, value in expected.items()):
                return path, original.encode("utf-8")
            if not replace_existing:
                raise SecretSetupError(f"{path}: ya contiene una configuración [secrets] diferente.")
            block = f'[secrets]\nbackend = "{backend}"\n{expected_key} = "{_relative(target, repo)}"\n'
            lines = original.splitlines(keepends=True)
            start = next(index for index, line in enumerate(lines) if line.strip() == "[secrets]")
            end = next(
                (
                    index
                    for index in range(start + 1, len(lines))
                    if re.match(r"^\s*\[[^\[][^]]*\]\s*(?:#.*)?$", lines[index])
                ),
                len(lines),
            )
            updated = "".join(lines[:start]) + block
            if end < len(lines):
                if not updated.endswith("\n\n"):
                    updated += "\n"
                updated += "".join(lines[end:])
            return path, updated.encode("utf-8")
    block_key = "file" if backend == "sops" else "gopass_file"
    block = f'[secrets]\nbackend = "{backend}"\n{block_key} = "{_relative(target, repo)}"\n'
    if original and not original.endswith("\n"):
        original += "\n"
    if original:
        original += "\n"
    return path, (original + block).encode("utf-8")


def _atomic_write(updates: dict[Path, bytes]) -> None:
    temporary: list[tuple[Path, Path]] = []
    try:
        for path, content in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            temporary.append((Path(name), path))
        for source, target in temporary:
            os.replace(source, target)
    finally:
        for source, _ in temporary:
            source.unlink(missing_ok=True)


def _prompt_sops(
    repo: Path,
    target: Path,
    input_fn: Callable[[str], str],
    secret_input_fn: Callable[[str], str],
) -> bytes:
    _require_command("sops")
    _require_command("age")
    model = input_fn("Modelo: ").strip()
    api_base = input_fn("API base (opcional): ").strip()
    api_key = secret_input_fn("API key: ")
    if not model:
        raise SecretSetupError("El modelo no puede estar vacío.")
    if not api_key:
        raise SecretSetupError("La API key no puede estar vacía.")
    payload = json.dumps({"model": model, "api_base": api_base, "api_key": api_key})
    encrypted = _encrypt_sops(payload, target, sops_command=_require_command("sops"), cwd=repo)
    if not encrypted.strip():
        raise SecretSetupError("SOPS no pudo cifrar las credenciales; revisa la configuración de age.")
    return encrypted.encode("utf-8")


def _gopass_references(repo: Path, prefix: str | None) -> tuple[bytes, list[str]]:
    _require_command("gopass")
    namespace = prefix.strip("/") if prefix else f"specnative/{_slug(repo.name)}"
    if not namespace:
        raise SecretSetupError("El prefijo gopass no puede estar vacío.")
    refs = {
        "model": f"{namespace}/model",
        "api_base": f"{namespace}/api-base",
        "api_key": f"{namespace}/api-key",
    }
    content = "[references]\n" + "".join(f'{key} = "{value}"\n' for key, value in refs.items())
    commands = [f"gopass insert {value}" for value in refs.values()]
    return content.encode("utf-8"), commands


def initialize_secrets(
    repo: Path,
    backend: str,
    *,
    secrets_file: Path | None = None,
    gopass_file: Path | None = None,
    prefix: str | None = None,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
) -> tuple[list[Path], list[str]]:
    repo = repo.resolve()
    if not repo.is_dir():
        raise SecretSetupError(f"El proyecto no existe: {repo}")
    if backend not in {"sops", "gopass"}:
        raise SecretSetupError("El backend debe ser `sops` o `gopass`.")
    target = repo / (secrets_file or DEFAULT_SOPS_FILE if backend == "sops" else gopass_file or DEFAULT_GOPASS_FILE)
    if not target.is_absolute():
        target = repo / target
    if target.exists():
        raise SecretSetupError(f"{target} ya existe; no se sobrescribirá.")

    instructions: list[str] = []
    if backend == "sops":
        content = _prompt_sops(repo, target, input_fn, secret_input_fn)
    else:
        content, instructions = _gopass_references(repo, prefix)
    config_path, config_content = _agent_config(repo, backend, target)
    updates = {target: content}
    if not config_path.exists() or config_path.read_bytes() != config_content:
        updates[config_path] = config_content
    _atomic_write(updates)
    return sorted(updates), instructions


def authenticate(
    repo: Path | None,
    *,
    confirm_replace: Callable[[str], bool],
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
) -> tuple[list[Path], bool]:
    """Prompt for credentials and encrypt them globally or for one project."""
    project = repo.resolve() if repo is not None else None
    if project is not None and not project.is_dir():
        raise SecretSetupError(f"El proyecto no existe: {project}")
    target = project / DEFAULT_SOPS_FILE if project is not None else global_sops_file()
    config_update: tuple[Path, bytes] | None = None
    if project is not None:
        config_update = _agent_config(project, "sops", target, replace_existing=True)
    config_would_change = bool(
        config_update is not None
        and config_update[0].exists()
        and config_update[0].read_bytes() != config_update[1]
    )
    if (target.exists() or config_would_change) and not confirm_replace(
        f"¿Reemplazar las credenciales/configuración ASN en {target.parent}?"
    ):
        return [], True
    tools = _require_auth_tools()

    model = input_fn("Modelo: ").strip()
    api_base = input_fn("API base (opcional; vacío para OpenAI): ").strip()
    api_key = secret_input_fn("API key (entrada oculta): ")
    if not model:
        raise SecretSetupError("El modelo no puede estar vacío.")
    if not api_key:
        raise SecretSetupError("La API key no puede estar vacía.")

    identity, recipient = _age_identity(tools)
    payload = json.dumps({"model": model, "api_base": api_base, "api_key": api_key})
    encrypted = _encrypt_sops(
        payload,
        target,
        sops_command=tools["sops"],
        recipient=recipient,
        identity=identity,
    )
    if not encrypted.strip():
        raise SecretSetupError("SOPS no devolvió un archivo cifrado.")
    updates = {target: encrypted.encode("utf-8")}
    if config_update is not None:
        updates[config_update[0]] = config_update[1]
    if project is None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target.parent, 0o700)
    _atomic_write(updates)
    return sorted(updates), False
