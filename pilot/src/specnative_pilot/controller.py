from __future__ import annotations

from pathlib import Path
from typing import Callable, TextIO

from .agent import SpecNativeAgent
from .config import Config
from .history import HistoryStore
from .intent import parse_template_command
from .mcp import SpecNativeMcp
from .model import build_model
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

    def run(self, initiative: str | None = None) -> int:
        history_path = self.config.repo / ".specnative" / "agent" / "sessions" / "latest.jsonl" if self.config.history else None
        history = HistoryStore(history_path)
        with SpecNativeMcp(self.config.repo, self.config.mcp_python, self.config.mcp_script) as mcp:
            initiative = initiative or self.choose_initiative(mcp)
            model = build_model(self.config)
            context = str(mcp.call("context_snapshot", initiative=initiative if (self.config.repo / "spec-native" / "specs" / initiative / "SPEC.md").exists() else ""))
            agent = SpecNativeAgent(model, mcp, initiative, self.config.question_mode, self.config.max_steps)
            self.say("Piloto SpecNative iniciado. Usa /template nombre, /help o /quit.")
            while True:
                message = self.input("\n> ").strip()
                if message in {"/quit", "/exit"}:
                    return 0
                if message == "/help":
                    self.say("Escribe la idea o responde preguntas. /template nombre aplica una plantilla sólo tras confirmación.")
                    continue
                if not message:
                    continue
                history.append("user", initiative=initiative, message=message)
                command = parse_template_command(message)
                if command is not None:
                    self.handle_template(mcp, initiative, command.name)
                    continue
                response = agent.run_turn(message, context)
                history.append("agent", initiative=initiative, response=response)
                self.say(response)
                self.apply_proposals(mcp, agent.proposals)
        return 0
