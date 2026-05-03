from typing import Any

from daemon.config import settings
from daemon.research.base import ResearchBundle
from daemon.research.deterministic_provider import DeterministicResearchProvider
from daemon.research.web_provider import WebResearchProvider


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_research_bundle(brief: dict[str, Any]) -> ResearchBundle:
    deterministic = DeterministicResearchProvider().run(brief)
    if brief.get("mode") != "auto_trend" or not settings.research_enable_web:
        for finding in deterministic.findings:
            evidence_json = dict(finding.get("evidence_json") or {})
            evidence_json.setdefault("provider", "deterministic_provider")
            evidence_json.setdefault("fallback", True)
            finding["evidence_json"] = evidence_json
        return deterministic

    web = WebResearchProvider(
        parse_csv(settings.research_allowed_urls),
        allowed_domains=parse_csv(settings.research_allowed_domains),
        timeout_seconds=settings.research_web_timeout_seconds,
        delay_seconds=settings.research_web_delay_seconds,
    )
    if not web.available():
        for finding in deterministic.findings:
            evidence_json = dict(finding.get("evidence_json") or {})
            evidence_json.setdefault("provider", "deterministic_provider")
            evidence_json.setdefault("fallback", True)
            evidence_json.setdefault("fallback_reason", "web_research_enabled_but_no_allowed_urls")
            finding["evidence_json"] = evidence_json
        deterministic.evidence.insert(
            0,
            {
                "provider": "web_provider",
                "fallback": True,
                "reason": "RESEARCH_ENABLE_WEB=true but RESEARCH_ALLOWED_URLS is empty or no domains are allowed",
            },
        )
        return deterministic

    web_bundle = web.run(brief)
    findings = [*web_bundle.findings, *deterministic.findings]
    for finding in deterministic.findings:
        evidence_json = dict(finding.get("evidence_json") or {})
        evidence_json.setdefault("provider", "deterministic_provider")
        evidence_json.setdefault("fallback", bool(not web_bundle.findings))
        finding["evidence_json"] = evidence_json

    evidence = [*web_bundle.evidence, *deterministic.evidence]
    for finding in findings:
        evidence_json = dict(finding.get("evidence_json") or {})
        evidence_json.setdefault("research_evidence", evidence[:8])
        finding["evidence_json"] = evidence_json
    return ResearchBundle(findings=findings, candidates=deterministic.candidates, evidence=evidence)
