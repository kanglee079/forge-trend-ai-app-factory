from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ResearchBundle:
    findings: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)


class ResearchProvider(Protocol):
    name: str

    def available(self) -> bool:
        ...

    def collect(self, brief: dict[str, Any]) -> list[dict[str, Any]]:
        ...

    def run(self, brief: dict[str, Any]) -> ResearchBundle:
        ...
