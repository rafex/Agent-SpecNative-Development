from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from smolagents.utils import AgentGenerationError

from specnative_pilot.config import Config
from specnative_pilot.controller import Controller, SpecNativeMcp


class FakeMcp:
    def __init__(self, listing: str):
        self.listing = listing
        self.calls = []

    def call(self, name, **arguments):
        self.calls.append((name, arguments))
        if name == "list_templates":
            return self.listing
        return "ok"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def config(tmp_path):
    return Config(tmp_path, "", None, "OPENAI_API_KEY", "single", False, 1, Path("python"), Path("mcp.py"))


def test_invalid_template_never_writes(tmp_path):
    output = StringIO()
    controller = Controller(config(tmp_path), input_fn=lambda _: "", output=output)
    mcp = FakeMcp("     feature-rest-endpoint          Nueva ruta\n")
    controller.handle_template(mcp, "demo", "missing")
    assert [name for name, _ in mcp.calls] == ["list_templates"]
    assert "Plantilla inexistente" in output.getvalue()


def test_rejected_template_never_applies(tmp_path):
    output = StringIO()
    answers = iter(["n"])
    controller = Controller(config(tmp_path), input_fn=lambda _: next(answers), output=output)
    mcp = FakeMcp("     feature-rest-endpoint          Nueva ruta\n")
    controller.handle_template(mcp, "demo", "feature-rest-endpoint")
    assert [name for name, _ in mcp.calls] == ["list_templates"]
    assert "Plantilla rechazada" in output.getvalue()


def test_failed_preflight_stops_before_model_or_writes(tmp_path):
    output = StringIO()
    controller = Controller(config(tmp_path), input_fn=lambda _: "", output=output)
    mcp = FakeMcp("unused")
    mcp.call = lambda name, **arguments: "Validation failed:\n  - missing context" if name == "validate" else "unexpected"

    assert controller.run_preflight(mcp) is False
    assert mcp.call("validate") == "Validation failed:\n  - missing context"
    assert "Validation failed" in output.getvalue()


def _write_initiative(repo, base, slug, artifact):
    folder = repo / "spec-native" / base / slug
    folder.mkdir(parents=True)
    (folder / artifact).write_text("", encoding="utf-8")


def test_choose_initiative_lists_existing_specs_and_tasks_once(tmp_path):
    _write_initiative(tmp_path, "specs", "portal-captive", "SPEC.md")
    _write_initiative(tmp_path, "tasks", "portal-captive", "TASKS.md")
    output = StringIO()
    controller = Controller(config(tmp_path), input_fn=lambda _: "portal-captive", output=output)

    assert controller.choose_initiative(FakeMcp("unused")) == "portal-captive"
    assert output.getvalue().count("portal-captive") == 1


def test_choose_initiative_reuses_similar_slug_when_new_slug_is_not_confirmed(tmp_path):
    _write_initiative(tmp_path, "specs", "portal-captive", "SPEC.md")
    answers = iter(["portal-captives", "n"])
    controller = Controller(config(tmp_path), input_fn=lambda _: next(answers), output=StringIO())

    assert controller.choose_initiative(FakeMcp("unused")) == "portal-captive"


def test_choose_initiative_allows_similar_new_slug_after_confirmation(tmp_path):
    _write_initiative(tmp_path, "specs", "portal-captive", "SPEC.md")
    answers = iter(["portal-captives", "s"])
    controller = Controller(config(tmp_path), input_fn=lambda _: next(answers), output=StringIO())

    assert controller.choose_initiative(FakeMcp("unused")) == "portal-captives"


def test_choose_initiative_accepts_new_slug_when_no_initiatives_exist(tmp_path):
    controller = Controller(config(tmp_path), input_fn=lambda _: "portal-captive", output=StringIO())

    assert controller.choose_initiative(FakeMcp("unused")) == "portal-captive"


def test_choose_initiative_case_insensitive_exact_match_uses_canonical_slug(tmp_path):
    _write_initiative(tmp_path, "specs", "portal-captive", "SPEC.md")
    controller = Controller(config(tmp_path), input_fn=lambda _: "PORTAL-CAPTIVE", output=StringIO())

    assert controller.choose_initiative(FakeMcp("unused")) == "portal-captive"


def test_interactive_initiative_prompt_enables_live_fuzzy_completion(tmp_path, monkeypatch):
    import sys

    class TTY:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", TTY())
    monkeypatch.setattr(sys, "stdout", TTY())
    calls = []

    def prompt(text, **kwargs):
        calls.append((text, kwargs))
        return "portal-captive"

    monkeypatch.setattr("prompt_toolkit.prompt", prompt)
    controller = Controller(config(tmp_path), output=StringIO())

    assert controller._initiative_prompt("Iniciativa: ", ["portal-captive"]) == "portal-captive"
    assert calls[0][0] == "Iniciativa: "
    assert calls[0][1]["complete_while_typing"] is True
    assert calls[0][1]["completer"].WORD is True


def test_one_edit_apart_covers_insert_delete_and_substitution():
    from specnative_pilot.controller import _one_edit_apart

    assert _one_edit_apart("portal-captive", "portal-captives")
    assert _one_edit_apart("portal-captive", "portal-capive")
    assert _one_edit_apart("portal-captive", "portal-captivf")
    assert not _one_edit_apart("portal-captive", "portal-captive")
    assert not _one_edit_apart("portal-captive", "unrelated")


def test_help_uses_mdcat_when_available(tmp_path, monkeypatch):
    output = StringIO()
    calls = []
    controller = Controller(config(tmp_path), output=output)

    monkeypatch.setattr("specnative_pilot.controller.shutil.which", lambda _: "/usr/bin/mdcat")

    def render(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="\u001b[1mRendered help\u001b[0m\n")

    monkeypatch.setattr("specnative_pilot.controller.subprocess.run", render)
    controller.show_help()

    assert calls[0][0][:3] == ["/usr/bin/mdcat", "--ansi", "--no-pager"]
    assert output.getvalue() == "\u001b[1mRendered help\u001b[0m\n"


def test_help_falls_back_to_markdown_when_mdcat_is_missing(tmp_path, monkeypatch):
    output = StringIO()
    controller = Controller(config(tmp_path), output=output)
    monkeypatch.setattr("specnative_pilot.controller.shutil.which", lambda _: None)

    controller.show_help()

    assert "# Ayuda de ASN" in output.getvalue()
    assert "/template <nombre>" in output.getvalue()


def test_generation_error_exits_cleanly_without_writes(tmp_path, monkeypatch):
    output = StringIO()
    controller = Controller(config(tmp_path), input_fn=lambda _: "describir idea", output=output)
    monkeypatch.setattr("specnative_pilot.controller.record_failure", lambda *args, **kwargs: None)
    mcp = FakeMcp("unused")
    monkeypatch.setattr("specnative_pilot.controller.SpecNativeMcp", lambda *_: mcp)

    class BrokenSession:
        closed = False

        def message(self, _):
            logger = SimpleNamespace(log_error=lambda _: None)
            raise AgentGenerationError("provider rejected tool call", logger)

        def close(self):
            self.closed = True

    session = BrokenSession()
    monkeypatch.setattr("specnative_pilot.controller.AgentSession.from_mcp", lambda *_args, **_kwargs: session)

    result = controller.run("portal-captive")

    assert result == 2
    assert session.closed
    assert "compatibles con tool calling" in output.getvalue()
    assert "No se modificaron archivos" in output.getvalue()
    assert "Traceback" not in output.getvalue()
    assert not [name for name, _ in mcp.calls if name.startswith("write_")]
