from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Callable
from uuid import uuid4

from .agent import SpecNativeAgent
from .config import Config
from .history import HistoryStore
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
        context = str(mcp.call("context_snapshot", initiative=initiative if spec_path.exists() else ""))
        agent = SpecNativeAgent(model, mcp, initiative, config.question_mode, config.max_steps)
        history_path = config.repo / ".specnative" / "agent" / "sessions" / "latest.jsonl" if config.history else None
        return cls(
            session_id or uuid4().hex,
            config,
            initiative,
            mcp,
            agent,
            HistoryStore(history_path),
            owns_mcp,
        ).with_context(context)

    def with_context(self, context: str) -> "AgentSession":
        self.context = context
        return self

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
        self.history.append("user", initiative=self.initiative, message=message)
        command = parse_template_command(message)
        if command is not None:
            listing = str(self.mcp.call("list_templates", template_type="spec"))
            if command.name is None:
                return self._result("template_list", listing)
            names = spec_template_names(listing)
            if command.name not in names:
                return self._result("template_invalid", f"Plantilla inexistente: {command.name}\n\n{listing}")
            token = token_urlsafe(24)
            self.pending = PendingAction(token, "template", self.initiative, template=command.name)
            return self._result(
                "approval_required",
                f"Plantilla: {command.name}\nIniciativa: {self.initiative}\nSe creará SPEC.md desde esta plantilla.",
                approval_token=token,
                action="template",
                template=command.name,
            )

        response = self.agent.run_turn(message, self.context)
        self.history.append("agent", initiative=self.initiative, response=response)
        proposals = tuple(self.agent.proposals)
        if proposals:
            token = token_urlsafe(24)
            self.pending = PendingAction(token, "proposals", self.initiative, proposals=proposals)
            return self._result(
                "approval_required",
                response,
                approval_token=token,
                action="proposals",
                proposals=[_proposal_dict(item) for item in proposals],
            )
        return self._result("question", response, proposals=[])

    def approve(self, token: str) -> dict[str, Any]:
        self._ensure_open()
        pending = self.pending
        if pending is None or pending.token != token:
            raise SessionError("Token de aprobación inválido o expirado.")
        if pending.kind == "template":
            result = str(self.mcp.call("apply_spec_template", template_name=pending.template, initiative=self.initiative))
        else:
            outputs = []
            for proposal in pending.proposals:
                if proposal.document == "spec":
                    outputs.append(self.mcp.call("write_spec", initiative=proposal.initiative, content=proposal.content))
                elif proposal.document == "tasks":
                    outputs.append(self.mcp.call("write_tasks", initiative=proposal.initiative, content=proposal.content))
                else:
                    raise SessionError(f"Documento no soportado: {proposal.document}")
            result = "\n".join(map(str, outputs))
        validation = str(self.mcp.call("validate"))
        health = str(self.mcp.call("health_check"))
        self.pending = None
        return self._result("applied", result, validation=validation, health_check=health)

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
                return {
                    "status": "credentials_missing",
                    "text": credential_setup_message(missing, config.api_key_env),
                }
        except SecretResolutionError as error:
            return {
                "status": "credentials_error",
                "text": f"No se pudieron resolver las credenciales ASN: {error}. Revisa el backend o ejecuta `asn --auth`.",
            }
        try:
            session = AgentSession.create(config, initiative)
        except InitiativeRequired as error:
            return {"status": "initiative_required", "initiatives": error.specs, "text": str(error)}
        except PreflightError as error:
            return {"status": "preflight_failed", "text": str(error)}
        except Exception as error:
            return {"status": "error", "text": str(error)}
        self.sessions[session.session_id] = session
        return session._result("ready", "Sesión ASN iniciada.")

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
