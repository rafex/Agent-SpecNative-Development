from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, TextIO

from smolagents.utils import AgentGenerationError

from .agent import SpecNativeAgent
from .config import Config
from .failure_log import record_failure
from .history import HistoryStore
from .intent import parse_template_command
from .mcp import SpecNativeMcp
from .model import build_model, find_empty_model_output_error, tool_call_attempts
from .session import AgentSession
from .templates import spec_template_names


class Controller:
    def __init__(self, config: Config, input_fn: Callable[[str], str] = input, output: TextIO | None = None) -> None:
        import sys
        self.config = config
        self.input = input_fn
        self.output = output or sys.stdout
        self.use_terminal_prompt = input_fn is input

    def say(self, message: str = "") -> None:
        print(message, file=self.output)

    def read_input(self, prompt: str) -> str:
        """Read an editable terminal line, preserving injected/non-TTY input."""
        import sys

        if self.use_terminal_prompt and sys.stdin.isatty() and sys.stdout.isatty():
            try:
                from prompt_toolkit import prompt as terminal_prompt
            except ImportError:
                pass
            else:
                return terminal_prompt(prompt)
        return self.input(prompt)

    def confirm(self, prompt: str) -> bool:
        return self.read_input(f"{prompt} [s/N] ").strip().lower() in {"s", "si", "sí", "y", "yes"}

    def show_help(self) -> None:
        help_path = Path(__file__).parent / "resources" / "specnative-agent" / "help.md"
        try:
            markdown = help_path.read_text(encoding="utf-8")
        except OSError:
            self.say("No se pudo cargar la ayuda de ASN desde el paquete instalado.")
            return

        mdcat = shutil.which("mdcat")
        if mdcat:
            try:
                rendered = subprocess.run(
                    [mdcat, "--ansi", "--no-pager", str(help_path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                rendered = None
            if rendered is not None and rendered.returncode == 0 and rendered.stdout:
                self.output.write(rendered.stdout)
                if not rendered.stdout.endswith("\n"):
                    self.output.write("\n")
                return
        self.say(markdown)

    def choose_initiative(self, mcp: SpecNativeMcp) -> str:
        initiatives = self._existing_initiatives()
        prompt = "Iniciativa (slug nuevo o existente): "
        value = self._initiative_prompt(prompt, initiatives).strip()
        if not value:
            raise RuntimeError("Debes indicar una iniciativa.")

        exact = next((item for item in initiatives if item.casefold() == value.casefold()), None)
        if exact is not None:
            return exact

        similar = self._one_edit_matches(value, initiatives)
        if similar:
            self.say("Iniciativa(s) existente(s) con nombre parecido: " + ", ".join(similar))
            if not self.confirm(f"¿Crear `{value}` de todas formas? Se creará una iniciativa distinta"):
                if len(similar) == 1:
                    return similar[0]
                chosen = self.read_input(f"Escribe el slug que quieres usar ({', '.join(similar)}): ").strip()
                canonical = next((item for item in similar if item.casefold() == chosen.casefold()), None)
                if canonical is None:
                    raise RuntimeError("Debes seleccionar una de las iniciativas existentes sugeridas.")
                return canonical
        return value

    def _existing_initiatives(self) -> list[str]:
        names: set[str] = set()
        for directory, artifact in (
            (self.config.repo / "spec-native" / "specs", "SPEC.md"),
            (self.config.repo / "spec-native" / "tasks", "TASKS.md"),
        ):
            if not directory.is_dir():
                continue
            for child in directory.iterdir():
                if child.is_dir() and (child / artifact).is_file():
                    names.add(child.name)
        return sorted(names, key=str.casefold)

    @staticmethod
    def _one_edit_matches(value: str, initiatives: list[str]) -> list[str]:
        normalized = value.strip().casefold()
        return [
            initiative
            for initiative in initiatives
            if _one_edit_apart(normalized, initiative.casefold())
        ]

    def _initiative_prompt(self, prompt: str, initiatives: list[str]) -> str:
        import sys

        if (
            not initiatives
            or not self.use_terminal_prompt
            or not sys.stdin.isatty()
            or not sys.stdout.isatty()
        ):
            if not initiatives:
                self.say("No hay iniciativas existentes. Puedes escribir un slug nuevo.")
            else:
                self.say("Iniciativas disponibles: " + ", ".join(initiatives))
            return self.read_input(prompt)

        try:
            from prompt_toolkit import prompt as terminal_prompt
            from prompt_toolkit.completion import FuzzyWordCompleter
        except ImportError:
            self.say("No se pudo cargar el autocompletado; puedes escribir un slug nuevo.")
            return self.read_input(prompt)

        completer = FuzzyWordCompleter(initiatives, WORD=True)
        return terminal_prompt(
            prompt,
            completer=completer,
            complete_while_typing=True,
            reserve_space_for_menu=min(6, len(initiatives)),
        )


    def handle_template(self, mcp: SpecNativeMcp, initiative: str, name: str | None) -> None:
        listing = str(mcp.call("list_templates", template_type="spec"))
        if not name:
            self.say(listing)
            return
        names = spec_template_names(listing)
        if name not in names:
            self.say(f"Plantilla inexistente: {name}\n\n{listing}")
            return
        self.say(f"Plantilla: {name}\nIniciativa: {initiative}\nSe creará SPEC.md desde esta plantilla.")
        if not self.confirm("¿Aplicar la plantilla?"):
            self.say("Plantilla rechazada; no se modificó ningún archivo.")
            return
        self.say(str(mcp.call("apply_spec_template", template_name=name, initiative=initiative)))
        self.say(str(mcp.call("validate")))

    def apply_proposals(self, mcp: SpecNativeMcp, proposals) -> None:
        if not proposals:
            return
        self.say("\nPropuestas detectadas:")
        for index, proposal in enumerate(proposals, 1):
            self.say(f"\n[{index}] {proposal.document}/{proposal.section}: {proposal.rationale}")
            self.say(proposal.content[:3000])
        if not self.confirm("¿Confirmar todas las propuestas?"):
            self.say("Propuestas rechazadas; no se modificó ningún archivo.")
            return
        for proposal in proposals:
            if proposal.document == "spec":
                self.say(str(mcp.call("write_spec", initiative=proposal.initiative, content=proposal.content)))
            elif proposal.document == "tasks":
                self.say(str(mcp.call("write_tasks", initiative=proposal.initiative, content=proposal.content)))
            else:
                self.say(f"Documento no soportado: {proposal.document}")
        self.say(str(mcp.call("validate")))
        self.say(str(mcp.call("health_check")))

    def run_preflight(self, mcp: SpecNativeMcp) -> bool:
        validation = str(mcp.call("validate"))
        self.say(validation)
        passed = validation.startswith("Validation passed")
        if not passed:
            record_failure(
                "preflight",
                RuntimeError(validation),
                model=self.config.model,
                endpoint=self.config.api_base,
            )
        return passed

    def run(self, initiative: str | None = None, preflight: bool = False) -> int:
        with SpecNativeMcp(self.config.repo, self.config.mcp_python, self.config.mcp_script) as mcp:
            if preflight and not self.run_preflight(mcp):
                self.say("Preflight SpecNative falló; no se inició el modelo ni se modificaron archivos.")
                return 2
            initiative = initiative or self.choose_initiative(mcp)
            session = AgentSession.from_mcp(self.config, initiative, mcp, owns_mcp=False)
            eval_log_path = getattr(session, "eval_log_path", None)
            model_id = getattr(session, "model_id", None) or self.config.model or "desconocido"
            self.say(f"Modelo activo: {model_id}")
            if eval_log_path is not None:
                self.say(f"Eval de llamadas al modelo: {eval_log_path}")
            self.say("Piloto SpecNative iniciado. Usa /help para ver comandos.")
            pending_failed_message: str | None = None
            pending_approval_token: str | None = None
            while True:
                message = self.read_input("\n> ").strip()
                if message in {"/quit", "/exit"}:
                    session.close()
                    return 0
                if message == "/help":
                    self.show_help()
                    continue
                if message == "/model":
                    self.say(f"Modelo activo en esta sesión: {model_id}")
                    continue
                if not message:
                    continue

                if pending_approval_token is not None:
                    if message == "/approve":
                        try:
                            applied = session.approve(pending_approval_token)
                        except Exception as error:
                            record_failure("approval", error, model=model_id, endpoint=self.config.api_base, include_traceback=True)
                            self.say(f"No se pudo aplicar la propuesta: {error}")
                            self.say("La propuesta sigue pendiente. Reintenta con /approve, usa /reject o /help.")
                            continue
                        pending_approval_token = None
                        self.say(str(applied.get("text", "")))
                        self.say(str(applied.get("validation", "")))
                        self.say(str(applied.get("health_check", "")))
                        self.say(f"Escritura realizada mediante: {applied.get('approval_backend', 'MCP')}")
                        continue
                    if message == "/reject":
                        self.say(session.reject(pending_approval_token)["text"])
                        pending_approval_token = None
                        continue
                    self.say("Hay una propuesta aprobada cuya escritura falló. Usa /approve para reintentar o /reject para descartarla.")
                    continue

                if pending_failed_message is not None:
                    if message == "/skip":
                        pending_failed_message = None
                        self.say("Turno fallido descartado; la sesión sigue activa.")
                        continue
                    if message == "/edit":
                        replacement = self.read_input("Nuevo mensaje (vacío o /cancel para conservar el anterior): ").strip()
                        if replacement and replacement != "/cancel":
                            pending_failed_message = replacement
                            self.say("Mensaje pendiente actualizado. Usa /retry para enviarlo o /skip para descartarlo.")
                        else:
                            self.say("Se conserva el mensaje fallido. Usa /retry o /skip.")
                        continue
                    if message == "/retry":
                        message = pending_failed_message
                    else:
                        self.say("Hay un turno fallido pendiente. Usa /retry, /edit o /skip antes de escribir otro mensaje.")
                        continue
                try:
                    result = session.message(message)
                except AgentGenerationError as error:
                    model = getattr(getattr(session, "agent", None), "model", None)
                    client_kwargs = getattr(model, "client_kwargs", {}) or {}
                    model_kwargs = getattr(model, "kwargs", {}) or {}
                    attempts = tool_call_attempts(error)
                    empty_output = find_empty_model_output_error(error)
                    record_failure(
                        "agent_generation",
                        error,
                        model=getattr(model, "model_id", None) or self.config.model,
                        endpoint=client_kwargs.get("base_url") or self.config.api_base,
                        api_key=client_kwargs.get("api_key"),
                        reasoning_effort=model_kwargs.get("reasoning_effort"),
                        attempts=attempts,
                        include_traceback=True,
                    )
                    pending_failed_message = message
                    if empty_output is not None:
                        self.say(
                            f"Error del modelo ({model_id}): {empty_output} ASN agotó el turno tras "
                            f"{attempts} intento(s). El texto queda en memoria para recuperarlo."
                        )
                    else:
                        self.say(
                            f"Error del modelo ({model_id}): no pudo completar una llamada a herramienta. "
                            "ASN requiere un modelo y endpoint compatibles con tool calling. "
                            f"ASN realizó {attempts} intento(s). El turno queda recuperable en esta sesión."
                        )
                    self.say("Usa /retry para repetir, /edit para corregir el mensaje o /skip para descartarlo. /model muestra el modelo activo.")
                    continue
                pending_failed_message = None
                if result.get("memory_warning"):
                    self.say(f"Aviso de memoria: {result['memory_warning']}")
                self.say(str(result.get("text", "")))
                if result.get("status") != "approval_required":
                    continue
                for proposal in result.get("proposals", []):
                    self.say(f"\n[{proposal['document']}/{proposal['section']}] {proposal['rationale']}")
                    self.say(proposal["content"][:3000])
                token = result["approval_token"]
                pending_approval_token = token
                if result.get("action") == "template":
                    required = {"apply_spec_template", "validate", "health_check"}
                else:
                    required = {"validate", "health_check"}
                    required.update(
                        "write_spec" if proposal["document"] == "spec" else "write_tasks"
                        for proposal in result.get("proposals", [])
                    )
                backend = mcp.approval_backend_for(required) if hasattr(mcp, "approval_backend_for") else "MCP del proyecto"
                self.say(f"Al aprobar, ASN usará: {backend}. Si no ofrece escritura, usará el MCP incluido con ASN.")
                if self.confirm("¿Confirmar la propuesta?"):
                    try:
                        applied = session.approve(token)
                    except Exception as error:
                        record_failure("approval", error, model=model_id, endpoint=self.config.api_base, include_traceback=True)
                        self.say(f"No se pudo aplicar la propuesta: {error}")
                        self.say("La propuesta sigue pendiente. Usa /approve para reintentar o /reject para descartarla.")
                        continue
                    pending_approval_token = None
                    self.say(str(applied.get("text", "")))
                    self.say(str(applied.get("validation", "")))
                    self.say(str(applied.get("health_check", "")))
                    self.say(f"Escritura realizada mediante: {applied.get('approval_backend', 'MCP')}")
                else:
                    self.say(session.reject(token)["text"])
                    pending_approval_token = None
        return 0


def _one_edit_apart(left: str, right: str) -> bool:
    """Return whether two strings differ by one insertion/deletion/substitution."""
    if left == right:
        return False
    if abs(len(left) - len(right)) > 1:
        return False

    i = j = edits = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(left) > len(right):
            i += 1
        elif len(right) > len(left):
            j += 1
        else:
            i += 1
            j += 1
    if i < len(left) or j < len(right):
        edits += 1
    return edits == 1
