from io import StringIO
from pathlib import Path

from specnative_pilot.config import Config
from specnative_pilot.controller import Controller


class FakeMcp:
    def __init__(self, listing: str):
        self.listing = listing
        self.calls = []

    def call(self, name, **arguments):
        self.calls.append((name, arguments))
        if name == "list_templates":
            return self.listing
        return "ok"


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
