from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, TextIO

from smolagents.utils import AgentGenerationError

from .agent import SpecNativeAgent
from .config import Config
from .history import HistoryStore
from .intent import parse_template_command
from .mcp import SpecNativeMcp
from .model import build_model
from .session import AgentSession
from .templates import spec_template_names


class Controller:
    def __init__(self, config: Config, input_fn: Callable[[str], str] = input, output: TextIO | None = None) -> None:
        import sys
        self.config = config
        self.input = input_fn
        self.output = output or sys.stdout

    def say(self, message: str = "") -> None:
        print(message, file=self.output)

    def confirm(self, prompt: str) -> bool:
        return self.input(f"{prompt} [s/N] ").strip().lower() in {"s", "si", "sí", "y", "yes"}

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
        specs = mcp.call("list_specs")
        self.say(str(specs))
        value = self.input("Iniciativa (slug nuevo o existente): ").strip()
        if not value:
            raise RuntimeError("Debes indicar una iniciativa.")
        return value

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
        return validation.startswith("Validation passed")

    def run(self, initiative: str | None = None, preflight: bool = False) -> int:
        with SpecNativeMcp(self.config.repo, self.config.mcp_python, self.config.mcp_script) as mcp:
            if preflight and not self.run_preflight(mcp):
                self.say("Preflight SpecNative falló; no se inició el modelo ni se modificaron archivos.")
                return 2
            initiative = initiative or self.choose_initiative(mcp)
            session = AgentSession.from_mcp(self.config, initiative, mcp, owns_mcp=False)
            self.say("Piloto SpecNative iniciado. Usa /template nombre, /help o /quit.")
            while True:
                message = self.input("\n> ").strip()
                if message in {"/quit", "/exit"}:
                    session.close()
                    return 0
                if message == "/help":
                    self.show_help()
                    continue
                if not message:
                    continue
                try:
                    result = session.message(message)
                except AgentGenerationError:
                    session.close()
                    self.say(
                        "Error del modelo: no pudo completar una llamada a herramienta. "
                        "ASN requiere un modelo y endpoint compatibles con tool calling. "
                        "Revisa la configuración del proveedor y vuelve a iniciar ASN. "
                        "No se modificaron archivos."
                    )
                    return 2
                self.say(str(result.get("text", "")))
                if result.get("status") != "approval_required":
                    continue
                for proposal in result.get("proposals", []):
                    self.say(f"\n[{proposal['document']}/{proposal['section']}] {proposal['rationale']}")
                    self.say(proposal["content"][:3000])
                token = result["approval_token"]
                if self.confirm("¿Confirmar la propuesta?"):
                    applied = session.approve(token)
                    self.say(str(applied.get("text", "")))
                    self.say(str(applied.get("validation", "")))
                    self.say(str(applied.get("health_check", "")))
                else:
                    self.say(session.reject(token)["text"])
        return 0
