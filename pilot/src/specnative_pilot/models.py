from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TemplateCommand:
    name: str | None


@dataclass(frozen=True)
class Proposal:
    initiative: str
    document: str
    section: str
    content: str
    rationale: str
    files: list[str] = field(default_factory=list)
