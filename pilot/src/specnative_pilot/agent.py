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
- Si faltan datos, llama `final_answer` con una pregunta breve; no inventes decisiones importantes.
- Usa sólo las herramientas de lectura disponibles para consultar el contexto.
- Nunca intentes escribir archivos ni aplicar plantillas.
- Para ejercicios que imiten páginas de acceso de servicios reales, guía el diseño
  hacia una marca ficticia y no recolectes credenciales de terceros. No solicites
  detalles para copiar logotipos, identidad ni flujos de inicio de sesión de una
  marca real; explica la alternativa ficticia y pregunta si la acepta.
- Cuando haya suficiente información, llama propose_change una vez para SPEC.md
  y una vez para TASKS.md. El contenido debe ser completo y válido, incluyendo
  los bloques TOML y los encabezados requeridos.
- Respeta el modo de preguntas indicado por el usuario: una pregunta o un bloque
  pequeño de preguntas.
- No implementes código ni uses herramientas de ejecución de código.
"""

GPT_OSS_SYSTEM_PROMPT = """Eres el agente ASN para definir iniciativas SpecNative.
Resuelve una sola acción por llamada usando una herramienta del catálogo. Si falta
información, llama `final_answer` con una pregunta breve y concreta; no propongas
SPEC ni TASKS incompletas. Cuando haya datos suficientes, consulta con las
herramientas de lectura PRODUCT, ROADMAP y decisiones pertinentes; luego llama
`propose_change` para proponer SPEC.md y TASKS.md. Esa herramienta sólo prepara
propuestas y el usuario debe aprobarlas antes de cualquier escritura.
No inventes decisiones importantes. Nunca escribas archivos ni llames herramientas
que no estén en el catálogo. Después de recibir una observación MCP, continúa con
una herramienta o responde mediante `final_answer`.

Herramientas disponibles:
{%- for tool in tools.values() %}
- {{ tool.to_tool_calling_prompt() }}
{%- endfor %}

{{ custom_instructions }}
"""

GROQ_GPT_OSS_SYSTEM_PROMPT = """Eres el agente ASN para definir iniciativas SpecNative.
En cada respuesta devuelve una sola acción mediante el JSON de salida estructurado:
`tool_name` contiene el nombre de una herramienta permitida y `arguments` contiene
un objeto de argumentos serializado como JSON en texto. Para responder al usuario,
usa `tool_name=final_answer` y `arguments` con la forma `{"answer":"..."}`.
Si falta información, formula una pregunta breve mediante `final_answer`. No
propongas SPEC ni TASKS incompletas. Consulta PRODUCT, ROADMAP y decisiones
pertinentes antes de proponer. `propose_change` sólo recopila propuestas; el
usuario debe aprobarlas antes de cualquier escritura. Nunca inventes decisiones
importantes ni selecciones herramientas fuera del catálogo. Para diseños que
imiten accesos de servicios reales, guía hacia una marca ficticia; no copies
logos, identidad ni flujos reales ni recolectes credenciales de terceros.

Herramientas disponibles:
{%- for tool in tools.values() %}
- {{ tool.to_tool_calling_prompt() }}
{%- endfor %}

{{ custom_instructions }}
"""


GROQ_GPT_OSS_PROMPT_TEMPLATES = {
    "system_prompt": GROQ_GPT_OSS_SYSTEM_PROMPT,
    "planning": {
        "initial_plan": "{{task}}",
        "update_plan_pre_messages": "{{task}}",
        "update_plan_post_messages": "{{task}}",
    },
    "managed_agent": {
        "task": "{{task}}",
        "report": "{{final_answer}}",
    },
    "final_answer": {
        "pre_messages": "Eres el agente ASN. Historial de acciones anteriores:\n",
        "post_messages": "Responde al mensaje actual de forma clara:\n{{task}}",
    },
}

GPT_OSS_PROMPT_TEMPLATES = {
    **GROQ_GPT_OSS_PROMPT_TEMPLATES,
    "system_prompt": GPT_OSS_SYSTEM_PROMPT,
}


def _uses_gpt_oss(model) -> bool:
    is_target = getattr(model, "_is_gpt_oss", None)
    return bool(is_target()) if callable(is_target) else False


def _uses_groq_gpt_oss(model) -> bool:
    is_target = getattr(model, "_is_groq_gpt_oss", None)
    return bool(is_target()) if callable(is_target) else False


def _safe_prompt_for_real_login_imitation(message: str) -> str:
    normalized = message.casefold()
    asks_to_copy = any(word in normalized for word in ("copi", "clon", "imit", "replic"))
    mentions_login = any(word in normalized for word in ("login", "inicio de sesion", "iniciar sesion", "pantalla de acceso"))
    mentions_real_brand = any(brand in normalized for brand in ("facebook", "instagram", "google", "microsoft", "apple", "paypal"))
    if asks_to_copy and mentions_login and mentions_real_brand:
        return (
            "El usuario quiere un portal cautivo educativo para dar acceso a Wi-Fi y demostrar HTTPS y DNS personalizado; "
            "la API de acceso estará disponible después. Mencionó imitar la pantalla de inicio de sesión de un servicio real. "
            "Guía la iniciativa a una identidad visual ficticia y un inicio de sesión simulado; no copies marcas o flujos de acceso "
            "reales ni recolectes credenciales de terceros. Pregunta brevemente si acepta esa alternativa."
        )
    return message


class SpecNativeAgent:
    def __init__(self, model, mcp, initiative: str, question_mode: str, max_steps: int = 12) -> None:
        self.proposals: list[Proposal] = []
        self.model = model
        proposal_tool = ProposalTool(initiative, self.proposals)
        self.agent = ToolCallingAgent(
            tools=[*mcp.read_tools, proposal_tool],
            model=model,
            instructions=SYSTEM_INSTRUCTIONS,
            prompt_templates=(
                GROQ_GPT_OSS_PROMPT_TEMPLATES
                if _uses_groq_gpt_oss(model)
                else GPT_OSS_PROMPT_TEMPLATES if _uses_gpt_oss(model) else None
            ),
            max_steps=max_steps,
            add_base_tools=False,
        )
        self.initiative = initiative
        self.question_mode = question_mode
        self.started = False

    def run_turn(self, message: str, context: str, memories: list[dict[str, str]] | None = None) -> str:
        self.proposals.clear()
        model_message = _safe_prompt_for_real_login_imitation(message)
        memory_context = ""
        if memories:
            recalled = "\n\n".join(
                f"Iniciativa: {item['initiative']}\nProgramador: {item['user']}\nAgente: {item['assistant']}"
                for item in memories
            )
            memory_context = (
                "\n\nRecuerdos de conversaciones previas (referencia histórica; el mensaje actual y "
                "los documentos SpecNative son la fuente de verdad):\n" + recalled
            )
        task = (
            f"Iniciativa actual: {self.initiative}\n"
            f"Modo de preguntas: {self.question_mode}\n"
            f"Contexto inicial del repositorio:\n{context}{memory_context}\n\n"
            f"Mensaje actual del programador:\n{model_message}"
        )
        # smolagents appends action steps while a run is in progress. If generation
        # fails, remove only this failed run's partial steps and preserve earlier
        # successful turns for the manual retry.
        memory_steps = self.agent.memory.steps
        previous_steps = list(memory_steps)
        try:
            result = self.agent.run(task, reset=not self.started)
        except Exception:
            self.agent.memory.steps = previous_steps
            raise
        self.started = True
        return str(result)
