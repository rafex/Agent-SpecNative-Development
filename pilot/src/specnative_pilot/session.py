from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Callable
from uuid import uuid4

from .agent import SpecNativeAgent
from .config import Config
from .failure_log import record_failure
from .history import EmbeddingClient, HistoryStore
from .intent import parse_template_command
from .mcp import SpecNativeMcp
from .model import build_model
from .models import Proposal
from .secrets import SecretResolutionError, credential_setup_message, missing_credential_names, resolve_credentials
from .templates import spec_template_names


class SessionError(RuntimeError):
    """A recoverable session error safe to return through MCP."""


class PreflightError(SessionError):
    pass


class InitiativeRequired(SessionError):
    def __init__(self, specs: str) -> None:
        super().__init__("Debes indicar una iniciativa antes de iniciar la sesión.")
        self.specs = specs


@dataclass(frozen=True)
class PendingAction:
    token: str
    kind: str
    initiative: str
    proposals: tuple[Proposal, ...] = ()
    template: str | None = None


def _proposal_dict(proposal: Proposal) -> dict[str, Any]:
    return asdict(proposal)


class AgentSession:
    """Shared stateful boundary used by the CLI and the MCP agent bridge."""

    def __init__(
        self,
        session_id: str,
        config: Config,
        initiative: str,
        mcp: SpecNativeMcp,
        agent: SpecNativeAgent,
        history: HistoryStore,
        owns_mcp: bool,
    ) -> None:
        self.session_id = session_id
        self.config = config
        self.initiative = initiative
        self.mcp = mcp
        self.agent = agent
        self.history = history
        self.owns_mcp = owns_mcp
        self.pending: PendingAction | None = None
        self.closed = False
        self._memory_warning_reported = False

    @classmethod
    def from_mcp(
        cls,
        config: Config,
        initiative: str,
        mcp: SpecNativeMcp,
        session_id: str | None = None,
        model_builder: Callable[[Config], Any] = build_model,
        owns_mcp: bool = False,
    ) -> "AgentSession":
        if not initiative.strip():
            raise SessionError("Debes indicar una iniciativa.")
        model = model_builder(config)
        spec_path = config.repo / "spec-native" / "specs" / initiative / "SPEC.md"
        groq_gpt_oss = getattr(model, "_is_groq_gpt_oss", None)
        if callable(groq_gpt_oss) and groq_gpt_oss():
            status = str(mcp.call("status"))
            if spec_path.exists():
                initiative_context = str(mcp.call("read_spec", initiative=initiative))
                context = (
                    f"Repositorio SpecNative validado. Estado: {status}\n"
                    f"Spec vigente de {initiative}:\n{initiative_context}\n"
                    "Consulta los documentos canónicos y decisiones con herramientas MCP de lectura cuando sean pertinentes."
                )
            else:
                context = (
                    f"Repositorio SpecNative validado. Estado: {status}\n"
                    f"No existe todavía SPEC.md para {initiative}. No inventes decisiones del producto; "
                    "consulta PRODUCT, ROADMAP o decisiones con herramientas MCP de lectura si son necesarias."
                )
        else:
            context = str(mcp.call("context_snapshot", initiative=initiative if spec_path.exists() else ""))
        agent = SpecNativeAgent(model, mcp, initiative, config.question_mode, config.max_steps)
        history_path = config.repo / ".specnative" / "agent" / "memory.sqlite3" if config.history else None
        history = HistoryStore(history_path)
        if config.history:
            if config.embedding_model:
                try:
                    credentials = resolve_credentials(config)
                    if credentials.api_key:
                        history.embedding_client = EmbeddingClient(
                            api_key=credentials.api_key,
                            model=config.embedding_model,
                            base_url=credentials.api_base,
                        )
                        history.vector_enabled = True
                        history.vector_error = None
                    else:
                        history.vector_enabled = False
                        history.vector_error = "Falta API key; la memoria queda disponible sin búsqueda vectorial."
                except (SecretResolutionError, RuntimeError) as error:
                    history.vector_enabled = False
                    history.vector_error = f"No se pudo configurar embeddings ({type(error).__name__}); el historial sigue activo."
            else:
                history.vector_enabled = False
                history.vector_error = "Búsqueda vectorial desactivada; configura [agent].embedding_model o SPECNATIVE_AGENT_EMBEDDING_MODEL."
        return cls(
            session_id or uuid4().hex,
            config,
            initiative,
            mcp,
            agent,
            history,
            owns_mcp,
        ).with_context(context)

    def with_context(self, context: str) -> "AgentSession":
        self.context = context
        return self

    @property
    def eval_log_path(self) -> Path | None:
        model = getattr(self.agent, "model", None)
        path = getattr(model, "eval_log_path", None)
        return Path(path) if path is not None else None

    @property
    def model_id(self) -> str:
        model = getattr(self.agent, "model", None)
        return str(getattr(model, "model_id", None) or self.config.model or "desconocido")

    @classmethod
    def create(
        cls,
        config: Config,
        initiative: str | None,
        session_id: str | None = None,
        model_builder: Callable[[Config], Any] = build_model,
    ) -> "AgentSession":
        mcp = SpecNativeMcp(config.repo, config.mcp_python, config.mcp_script)
        mcp.__enter__()
        try:
            validation = str(mcp.call("validate"))
            if not validation.startswith("Validation passed"):
                raise PreflightError(validation)
            if not initiative:
                raise InitiativeRequired(str(mcp.call("list_specs")))
            return cls.from_mcp(config, initiative, mcp, session_id, model_builder, owns_mcp=True)
        except Exception:
            mcp.__exit__(None, None, None)
            raise

    def _ensure_open(self) -> None:
        if self.closed:
            raise SessionError("La sesión ya fue cerrada.")

    def _ensure_no_pending(self) -> None:
        if self.pending is not None:
            raise SessionError("Existe una propuesta pendiente; debes aprobarla o rechazarla primero.")

    def _result(self, status: str, text: str, **extra: Any) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": status,
            "session_id": self.session_id,
            "initiative": self.initiative,
            "text": text,
        }
        result.update(extra)
        return result

    def message(self, message: str) -> dict[str, Any]:
        self._ensure_open()
        self._ensure_no_pending()
        message = message.strip()
        if not message:
            raise SessionError("El mensaje no puede estar vacío.")
        command = parse_template_command(message)
        if command is not None:
            listing = str(self.mcp.call("list_templates", template_type="spec"))
            if command.name is None:
                return self._complete_turn(message, "template_list", listing)
            names = spec_template_names(listing)
            if command.name not in names:
                return self._complete_turn(message, "template_invalid", f"Plantilla inexistente: {command.name}\n\n{listing}")
            token = token_urlsafe(24)
            self.pending = PendingAction(token, "template", self.initiative, template=command.name)
            return self._complete_turn(
                message,
                "approval_required",
                f"Plantilla: {command.name}\nIniciativa: {self.initiative}\nSe creará SPEC.md desde esta plantilla.",
                approval_token=token,
                action="template",
                template=command.name,
            )

        memories = self.history.recall(message, initiative=self.initiative)
        response = self.agent.run_turn(message, self.context, memories=memories)
        proposals = tuple(self.agent.proposals)
        if proposals:
            token = token_urlsafe(24)
            self.pending = PendingAction(token, "proposals", self.initiative, proposals=proposals)
            return self._complete_turn(
                message,
                "approval_required",
                response,
                approval_token=token,
                action="proposals",
                proposals=[_proposal_dict(item) for item in proposals],
            )
        return self._complete_turn(message, "question", response, proposals=[])

    def _complete_turn(self, user_message: str, status: str, text: str, **extra: Any) -> dict[str, Any]:
        self.history.record_turn(
            user_message,
            text,
            initiative=self.initiative,
            session_id=self.session_id,
        )
        warning = self.history.vector_error if not self._memory_warning_reported else None
        if warning:
            self._memory_warning_reported = True
            extra["memory_warning"] = warning
        return self._result(status, text, **extra)

    def approve(self, token: str) -> dict[str, Any]:
        self._ensure_open()
        pending = self.pending
        if pending is None or pending.token != token:
            raise SessionError("Token de aprobación inválido o expirado.")
        if pending.kind == "template":
            required = {"apply_spec_template", "validate", "health_check"}
        else:
            required = {"validate", "health_check"}
            for proposal in pending.proposals:
                if proposal.document == "spec":
                    required.add("write_spec")
                elif proposal.document == "tasks":
                    required.add("write_tasks")
                else:
                    raise SessionError(f"Documento no soportado: {proposal.document}")
        with self.mcp.approved_calls(required) as call:
            if pending.kind == "template":
                result = str(call("apply_spec_template", template_name=pending.template, initiative=self.initiative))
            else:
                outputs = []
                for proposal in pending.proposals:
                    tool = "write_spec" if proposal.document == "spec" else "write_tasks"
                    outputs.append(call(tool, initiative=proposal.initiative, content=proposal.content))
                result = "\n".join(map(str, outputs))
            validation = str(call("validate"))
            health = str(call("health_check"))
        self.pending = None
        return self._result(
            "applied", result, validation=validation, health_check=health,
            approval_backend=getattr(self.mcp, "approval_backend", "MCP del proyecto"),
        )

    def reject(self, token: str) -> dict[str, Any]:
        self._ensure_open()
        pending = self.pending
        if pending is None or pending.token != token:
            raise SessionError("Token de aprobación inválido o expirado.")
        self.pending = None
        return self._result("rejected", "Propuesta rechazada; no se modificó ningún archivo.")

    def status(self) -> dict[str, Any]:
        self._ensure_open()
        return self._result(
            "approval_required" if self.pending else "ready",
            "Sesión activa.",
            pending=bool(self.pending),
            approval_token=self.pending.token if self.pending else None,
        )

    def close(self) -> dict[str, Any]:
        if not self.closed:
            self.closed = True
            if self.owns_mcp:
                self.mcp.__exit__(None, None, None)
        return {"status": "closed", "session_id": self.session_id}


class SessionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.sessions: dict[str, AgentSession] = {}

    def start(self, initiative: str | None, question_mode: str | None = None) -> dict[str, Any]:
        config = self.config
        if question_mode:
            config = replace(config, question_mode=question_mode)
        try:
            credentials = resolve_credentials(config)
            missing = missing_credential_names(config, credentials)
            if missing:
                record_failure(
                    "agent_mcp_start",
                    RuntimeError(credential_setup_message(missing, config.api_key_env)),
                    model=credentials.model,
                    endpoint=credentials.api_base,
                    api_key=credentials.api_key,
                )
                return {
                    "status": "credentials_missing",
                    "text": credential_setup_message(missing, config.api_key_env),
                }
        except SecretResolutionError as error:
            record_failure("agent_mcp_credentials", error, model=config.model, endpoint=config.api_base)
            return {
                "status": "credentials_error",
                "text": f"No se pudieron resolver las credenciales ASN: {error}. Revisa el backend o ejecuta `asn --auth`.",
            }
        try:
            session = AgentSession.create(config, initiative)
        except InitiativeRequired as error:
            record_failure("agent_mcp_start", error, model=config.model, endpoint=config.api_base)
            return {"status": "initiative_required", "initiatives": error.specs, "text": str(error)}
        except PreflightError as error:
            record_failure("agent_mcp_preflight", error, model=config.model, endpoint=config.api_base)
            return {"status": "preflight_failed", "text": str(error)}
        except Exception as error:
            record_failure(
                "agent_mcp_start",
                error,
                model=config.model,
                endpoint=config.api_base,
                include_traceback=True,
            )
            return {"status": "error", "text": str(error)}
        self.sessions[session.session_id] = session
        return session._result(
            "ready",
            "Sesión ASN iniciada.",
            model=session.model_id,
            eval_log=str(session.eval_log_path) if session.eval_log_path is not None else None,
        )

    def get(self, session_id: str) -> AgentSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionError("Sesión inexistente.")
        return session

    def close(self, session_id: str) -> dict[str, Any]:
        session = self.get(session_id)
        result = session.close()
        self.sessions.pop(session_id, None)
        return result
