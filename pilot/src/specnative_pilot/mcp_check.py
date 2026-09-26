from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from smolagents import ToolCallingAgent
from smolagents.monitoring import LogLevel
from smolagents.utils import AgentGenerationError

from .config import Config
from .mcp import SpecNativeMcp
from .model import build_model, tool_call_attempts


_MCP_TOOL = "status"
_FINAL_MARKER = "ASN_MCP_OK"
_DIAGNOSTIC_INSTRUCTIONS = (
    "Estás ejecutando una prueba técnica de integración. Llama exactamente una vez "
    "la herramienta status sin argumentos. Después de recibir el resultado, llama "
    f"final_answer con el texto exacto {_FINAL_MARKER}. No llames otras herramientas "
    "ni describas el resultado de status."
)
_DIAGNOSTIC_TASK = "Comprueba el ciclo de una herramienta MCP de lectura y finaliza la prueba."


@dataclass(frozen=True)
class AgentMcpTestResult:
    model: str
    elapsed_ms: float
    request_count: int
    eval_log_path: Path | None


class AgentMcpTestError(RuntimeError):
    def __init__(
        self,
        stage: str,
        message: str,
        *,
        request_count: int = 0,
        eval_log_path: Path | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.request_count = request_count
        self.eval_log_path = eval_log_path
        self.asn_tool_call_attempts = max(1, attempts)


def _tool_names(agent: ToolCallingAgent) -> list[str]:
    names: list[str] = []
    for step in agent.memory.steps:
        message = getattr(step, "model_output_message", None)
        for call in getattr(message, "tool_calls", None) or []:
            function = getattr(call, "function", None)
            name = getattr(function, "name", None)
            if name:
                names.append(name)
    return names


def _status_steps(agent: ToolCallingAgent) -> list[Any]:
    return [
        step
        for step in agent.memory.steps
        if _MCP_TOOL in [
            getattr(getattr(call, "function", None), "name", None)
            for call in (getattr(getattr(step, "model_output_message", None), "tool_calls", None) or [])
        ]
    ]


def _request_count(model: Any) -> int:
    return int(getattr(getattr(model, "eval_log", None), "request_count", 0))


def _eval_path(model: Any) -> Path | None:
    value = getattr(model, "eval_log_path", None)
    return Path(value) if value is not None else None


def check_agent_mcp(
    config: Config,
    *,
    model_builder: Callable[[Config], Any] = build_model,
    mcp_factory: Callable[..., SpecNativeMcp] = SpecNativeMcp,
) -> AgentMcpTestResult:
    """Run one live model → read-only MCP tool → model completion cycle."""
    started = time.perf_counter()
    model = model_builder(config)
    eval_path = _eval_path(model)
    try:
        with mcp_factory(config.repo, config.mcp_python, config.mcp_script) as mcp:
            tools = [tool for tool in mcp.read_tools if getattr(tool, "name", None) == _MCP_TOOL]
            if not tools:
                raise AgentMcpTestError(
                    "MCP discovery",
                    "El servidor MCP no anuncia la herramienta de lectura status.",
                    eval_log_path=eval_path,
                )

            agent = ToolCallingAgent(
                tools=tools,
                model=model,
                instructions=_DIAGNOSTIC_INSTRUCTIONS,
                max_steps=3,
                add_base_tools=False,
                verbosity_level=LogLevel.OFF,
            )
            try:
                answer = str(agent.run(_DIAGNOSTIC_TASK)).strip()
            except Exception as error:
                names = _tool_names(agent)
                status_called = _MCP_TOOL in names
                stage = "continuación tras MCP" if status_called else "tool calling del modelo"
                raise AgentMcpTestError(
                    stage,
                    f"El ciclo de diagnóstico falló ({type(error).__name__}).",
                    request_count=_request_count(model),
                    eval_log_path=eval_path,
                    attempts=tool_call_attempts(error) if isinstance(error, AgentGenerationError) else 1,
                ) from error

            status_steps = _status_steps(agent)
            if not status_steps:
                raise AgentMcpTestError(
                    "ejecución de MCP",
                    "El agente terminó sin ejecutar la herramienta MCP status.",
                    request_count=_request_count(model),
                    eval_log_path=eval_path,
                )
            failed_step = next((step for step in status_steps if getattr(step, "error", None) is not None), None)
            if failed_step is not None:
                error = failed_step.error
                raise AgentMcpTestError(
                    "ejecución de MCP",
                    f"La herramienta status falló ({type(error).__name__}).",
                    request_count=_request_count(model),
                    eval_log_path=eval_path,
                )
            if answer != _FINAL_MARKER or "final_answer" not in _tool_names(agent):
                raise AgentMcpTestError(
                    "continuación tras MCP",
                    "La herramienta status respondió, pero el agente no completó la respuesta de control.",
                    request_count=_request_count(model),
                    eval_log_path=eval_path,
                )
    except AgentMcpTestError:
        raise
    except Exception as error:
        raise AgentMcpTestError(
            "inicio de MCP",
            f"No se pudo iniciar o consultar el servidor MCP ({type(error).__name__}).",
            request_count=_request_count(model),
            eval_log_path=eval_path,
        ) from error

    return AgentMcpTestResult(
        model=getattr(model, "model_id", None) or config.model,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        request_count=_request_count(model),
        eval_log_path=eval_path,
    )
