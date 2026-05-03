import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from daemon.research.base import ResearchBundle


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.capture = True
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        if tag in {"script", "style", "noscript"}:
            self.capture = False

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.capture = True

    def handle_data(self, data: str) -> None:
        if self.capture:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


class WebResearchProvider:
    name = "web_provider"

    def __init__(self, urls: list[str], *, allowed_domains: list[str], timeout_seconds: float = 8.0, delay_seconds: float = 1.0) -> None:
        self.urls = urls
        self.allowed_domains = {domain.lower() for domain in allowed_domains}
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds

    def available(self) -> bool:
        allowed_urls = [url for url in self.urls if url.strip()]
        return bool(allowed_urls and self.allowed_domains)

    def collect(self, brief: dict[str, Any]) -> list[dict[str, Any]]:
        return self.run(brief).findings

    def run(self, brief: dict[str, Any]) -> ResearchBundle:
        evidence: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        for url in self.urls[:3]:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not parsed.scheme.startswith("http") or not self._allowed(domain):
                evidence.append({"provider": self.name, "source_url": url, "status": "skipped", "reason": "domain_not_allowed", "fallback": True})
                continue
            try:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    response = client.get(url, headers={"User-Agent": "ForgeTrendResearch/0.1 (+local operator)"})
                content_type = response.headers.get("content-type", "")
                text = response.text
                if "html" in content_type:
                    parser = TextExtractor()
                    parser.feed(text[:300000])
                    text = parser.text()
                summary = " ".join(text.split())[:900]
                extracted_chars = len(summary)
                evidence_item = {
                    "provider": self.name,
                    "source_url": str(response.url),
                    "http_status": response.status_code,
                    "content_type": content_type,
                    "extracted_chars": extracted_chars,
                    "fallback": False,
                }
                evidence.append(evidence_item)
                if response.status_code < 400 and summary:
                    findings.append(
                        {
                            "source": self.name,
                            "title": f"Web signal from {domain}",
                            "summary": summary,
                            "category": brief.get("target_category"),
                            "keywords": [domain, "web", "trend"],
                            "pain_points": ["Validate this signal manually before release decisions."],
                            "competitor_gaps": ["External web evidence needs review and synthesis."],
                            "evidence_json": evidence_item,
                            "confidence_score": 55,
                        }
                    )
            except Exception as exc:
                evidence.append({"provider": self.name, "source_url": url, "status": "failed", "reason": str(exc), "fallback": True})
            time.sleep(self.delay_seconds)
        return ResearchBundle(findings=findings, candidates=[], evidence=evidence)

    def _allowed(self, domain: str) -> bool:
        if not self.allowed_domains:
            return False
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in self.allowed_domains)
