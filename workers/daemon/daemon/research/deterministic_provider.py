from typing import Any

from daemon.research.base import ResearchBundle


class DeterministicResearchProvider:
    name = "deterministic"

    def __init__(self, findings_fn, candidates_fn) -> None:
        self.findings_fn = findings_fn
        self.candidates_fn = candidates_fn

    def run(self, brief: dict[str, Any]) -> ResearchBundle:
        findings = self.findings_fn(brief)
        candidates = self.candidates_fn(brief, findings)
        return ResearchBundle(findings=findings, candidates=candidates, evidence=[{"provider": self.name, "method": "brief_heuristics"}])
