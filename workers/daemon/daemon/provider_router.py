from __future__ import annotations

from dataclasses import dataclass

from daemon.provider_adapters import AIDER, CODEX_CLI, check_codex_authenticated, ProviderUnavailable


@dataclass(frozen=True)
class ProviderRoute:
    provider: str
    reason: str
    fallback_allowed: bool = True


def choose_code_provider(*, codex_enabled: bool, aider_enabled: bool = False, budget_available: bool = True) -> ProviderRoute:
    if not budget_available:
        return ProviderRoute("human_review", "Budget exceeded; no LLM provider should be called.", fallback_allowed=False)
    if codex_enabled and CODEX_CLI.available:
        try:
            check_codex_authenticated()
            return ProviderRoute("codex_cli", "Codex CLI is enabled and authenticated.")
        except ProviderUnavailable as exc:
            return ProviderRoute("deterministic", f"Codex unavailable: {exc}. Falling back deterministic.")
    if aider_enabled and AIDER.available:
        return ProviderRoute("aider", "Aider CLI is available for optional refinement.")
    return ProviderRoute("deterministic", "Deterministic generator is the safe default fallback.")
