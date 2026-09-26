from __future__ import annotations

from typing import Callable

from smolagents import Tool, ToolCallingAgent

from .models import Proposal


class ProposalTool(Tool):
    name = "propose_change"
    description = "Registra una propuesta completa de SPEC.md o TASKS.md para que el usuario la revise. Nunca escribe archivos."
    inputs = {
        "document": {"type": "string", "description": "spec o tasks"},
        "section": {"type": "string", "description": "complete o el nombre de la sección"},
        "content": {"type": "string", "description": "Contenido completo propuesto del archivo"},
        "rationale": {"type": "string", "description": "Por qué se propone el cambio"},
        "files": {"type": "array", "items": {"type": "string"}, "nullable": True, "description": "Archivos que cambiarían"},
    }
    output_type = "string"

    def __init__(self, initiative: str, collector: list[Proposal]) -> None:
        self.initiative = initiative
        self.collector = collector
        self.is_initialized = True

    def forward(self, document: str, section: str, content: str, rationale: str, files: list[str] | None = None) -> str:
        self.collector.append(Proposal(self.initiative, document, section, content, rationale, files or []))
        return "Propuesta registrada para revisión del usuario; no se modificó ningún archivo."


SYSTEM_INSTRUCTIONS = """Eres un agente especializado en definir software con SpecNative.

Reglas obligatorias:
- Ayuda a aclarar una idea mediante preguntas sobre problema, usuarios, objetivo,
  alcance, requisitos, criterios de aceptación, riesgos y dependencias.
- Si faltan datos, pregunta; no inventes decisiones importantes.
- Usa sólo las herramientas de lectura disponibles para consultar el contexto.
- Nunca intentes escribir archivos ni aplicar plantillas.
- Cuando haya suficiente información, llama propose_change una vez para SPEC.md
  y una vez para TASKS.md. El contenido debe ser completo y válido, incluyendo
  los bloques TOML y los encabezados requeridos.
- Respeta el modo de preguntas indicado por el usuario: una pregunta o un bloque
  pequeño de preguntas.
- No implementes código ni uses herramientas de ejecución de código.
"""


class SpecNativeAgent:
    def __init__(self, model, mcp, initiative: str, question_mode: str, max_steps: int = 12) -> None:
        self.proposals: list[Proposal] = []
        self.model = model
        proposal_tool = ProposalTool(initiative, self.proposals)
        self.agent = ToolCallingAgent(
            tools=[*mcp.read_tools, proposal_tool],
            model=model,
            instructions=SYSTEM_INSTRUCTIONS,
            max_steps=max_steps,
            add_base_tools=False,
        )
        self.initiative = initiative
        self.question_mode = question_mode
        self.started = False

    def run_turn(self, message: str, context: str) -> str:
        self.proposals.clear()
        task = (
            f"Iniciativa actual: {self.initiative}\n"
            f"Modo de preguntas: {self.question_mode}\n"
            f"Contexto inicial del repositorio:\n{context}\n\n"
            f"Mensaje del programador:\n{message}"
        )
        result = self.agent.run(task, reset=not self.started)
        self.started = True
        return str(result)
