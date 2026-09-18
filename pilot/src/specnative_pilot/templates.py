from __future__ import annotations

import re


def spec_template_names(text: str) -> set[str]:
    section = text.split("── Decision snippets", 1)[0]
    return set(re.findall(r"^\s{5,}([a-z0-9][a-z0-9-]*)\s{2,}", section, re.MULTILINE))
