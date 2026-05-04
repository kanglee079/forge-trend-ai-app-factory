from __future__ import annotations

from typing import Any


def _enabled_by_slug(runtime_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("slug")): item for item in runtime_config.get("enabled_skills", []) if item.get("slug")}


def select_skills(
    *,
    brief: dict[str, Any] | None,
    runtime_config: dict[str, Any],
    previous_failure: str | None = None,
    quality_issues: list[str] | None = None,
) -> list[dict[str, Any]]:
    enabled = _enabled_by_slug(runtime_config)
    selected: list[dict[str, Any]] = []

    def add(slug: str, reason: str) -> None:
        skill = enabled.get(slug)
        if not skill or any(item.get("slug") == slug for item in selected):
            return
        selected.append({**skill, "reason": reason})

    target_language = str((brief or {}).get("target_language") or "").lower()
    monetization = str((brief or {}).get("monetization_mode") or "").lower()
    category = str((brief or {}).get("target_category") or "").lower()
    prompt = str((brief or {}).get("raw_prompt") or "").lower()
    failures = " ".join([previous_failure or "", " ".join(quality_issues or [])]).lower()

    add("trend_research", "Score opportunities by demand, pain, feasibility, originality, and policy risk.")
    add("flutter_store_ready", "Generate a complete app candidate instead of a generic scaffold.")
    add("qa_flutter_fix", "Prepare the repair loop for Flutter analyze/test/build failures.")
    add("prompt_compression", "Keep agent context compact and reusable.")

    if target_language == "vi" or "người việt" in prompt or "vietnamese" in prompt:
        add("vietnamese_ux_writer", "Vietnamese-first target needs natural domain-specific UX copy.")
    if monetization in {"iap", "subscription", "freemium", "hybrid"}:
        add("iap_subscription_placeholder", "Monetization requires simulated billing disclosure and human review.")
    if category in {"education", "health", "finance"} or "policy" in failures:
        add("google_play_policy", "Higher policy sensitivity requires explicit policy gate context.")
    if "generic" in failures or "placeholder" in failures or "weak" in failures:
        add("flutter_store_ready", "Previous issue indicates generic output; deepen core flow.")
        add("code_review", "Review generated code for incomplete flows and regressions.")
    if "store" in failures or monetization:
        add("app_store_readiness", "Store readiness and tester package need explicit blockers.")
        add("aso_listing", "Create safe listing drafts for human review.")
    if "privacy" in failures or category in {"health", "finance", "education"}:
        add("privacy_policy", "Sensitive categories need clearer privacy posture.")

    try:
        token_budget = int(float((brief or {}).get("max_cost_usd") or 0))
    except (TypeError, ValueError):
        token_budget = 0
    if token_budget <= 0:
        return selected[:4]
    return selected[:8]
