from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .secrets import DEFAULT_GOPASS_FILE, DEFAULT_SOPS_FILE


class SecretSetupError(RuntimeError):
    """Raised when secret backend initialization cannot complete safely."""


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


def _agent_config(repo: Path, backend: str, target: Path) -> tuple[Path, bytes]:
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
            raise SecretSetupError(f"{path}: ya contiene una configuración [secrets] diferente.")
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
    result = subprocess.run(
        [
            "sops",
            "encrypt",
            "--input-type",
            "json",
            "--output-type",
            "yaml",
            "--filename-override",
            str(target),
        ],
        cwd=str(repo),
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise SecretSetupError("SOPS no pudo cifrar las credenciales; revisa la configuración de age.")
    return result.stdout.encode("utf-8")


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
