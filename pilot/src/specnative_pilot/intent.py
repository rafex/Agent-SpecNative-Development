from __future__ import annotations

import re

from .models import TemplateCommand

_TEMPLATE_COMMAND = re.compile(r"^\s*/template(?:\s+(?P<name>[a-z0-9][a-z0-9-]*))?\s*$", re.I)


def parse_template_command(text: str) -> TemplateCommand | None:
    """Parse only an explicit, standalone /template command."""
    match = _TEMPLATE_COMMAND.fullmatch(text)
    if not match:
        return None
    return TemplateCommand(name=match.group("name"))
