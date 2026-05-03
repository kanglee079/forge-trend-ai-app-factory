from typing import Any

from daemon.research.base import ResearchBundle


def first_sentence(value: str, fallback: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        return fallback
    for marker in [". ", "! ", "? "]:
        if marker in normalized:
            return normalized.split(marker, 1)[0].strip()
    return normalized[:180]


def derive_focus_terms(brief: dict[str, Any]) -> list[str]:
    raw = f"{brief.get('title', '')} {brief.get('raw_prompt', '')} {brief.get('target_category') or ''}".lower()
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "app",
        "build",
        "make",
        "create",
        "best",
        "trend",
        "search",
        "auto",
        "mobile",
        "user",
        "users",
        "have",
        "from",
        "into",
        "your",
        "their",
        "mvp",
    }
    terms: list[str] = []
    for token in "".join(char if char.isalnum() else " " for char in raw).split():
        if len(token) < 3 or token in stopwords:
            continue
        if token not in terms:
            terms.append(token)
    return terms[:8] or ["focused", "workflow", "assistant"]


def monetization_text(brief: dict[str, Any]) -> str:
    modes: list[str] = []
    if brief.get("iap_enabled"):
        modes.append("one-time in-app purchases for advanced packs or exports")
    if brief.get("subscription_enabled"):
        modes.append("subscription for ongoing coaching, sync, or premium automation")
    if brief.get("ads_enabled"):
        modes.append("careful ad placement after the core workflow is proven")
    if brief.get("monetization_mode") and brief.get("monetization_mode") != "none":
        modes.append(str(brief["monetization_mode"]).replace("_", " "))
    return "; ".join(modes) if modes else "Validate retention first, then add freemium upgrade points after human review."


def deterministic_findings(brief: dict[str, Any]) -> list[dict[str, Any]]:
    terms = derive_focus_terms(brief)
    category = brief.get("target_category") or terms[0].title()
    prompt_summary = first_sentence(str(brief.get("raw_prompt") or ""), "User wants the factory to identify a strong app opportunity.")
    return [
        {
            "source": "brief_intent",
            "title": f"{category} intent signal",
            "summary": prompt_summary,
            "category": category,
            "keywords": terms,
            "pain_points": [
                "Users need a clearer next action instead of another generic tracker.",
                "Existing tools often require too much setup before value appears.",
                "Trust, privacy, and originality need to be visible in the first session.",
            ],
            "competitor_gaps": [
                "Broad apps optimize for feature count instead of one repeated workflow.",
                "Onboarding rarely adapts to the user's first concrete goal.",
                "Monetization is often bolted on before the free value loop is proven.",
            ],
            "evidence_json": {"method": "deterministic_brief_analysis", "terms": terms},
            "confidence_score": 72,
        },
        {
            "source": "product_heuristic",
            "title": "MVP feasibility pattern",
            "summary": "A compact mobile app with onboarding, dashboard, guided actions, and settings can be built and tested by the current pipeline.",
            "category": category,
            "keywords": [*terms[:4], "onboarding", "dashboard", "qa"],
            "pain_points": [
                "Complex backend dependencies increase first-build failure risk.",
                "Thin scaffolds feel unfinished if the home screen has no state model.",
            ],
            "competitor_gaps": [
                "Many starter apps lack release policy checks.",
                "Most generated prototypes do not expose QA status and artifacts to the operator.",
            ],
            "evidence_json": {"pipeline_fit": "flutter_template_plus_codex_pass", "target_platforms": brief.get("target_platforms", ["android"])},
            "confidence_score": 68,
        },
        {
            "source": "monetization_fit",
            "title": "Revenue and policy fit",
            "summary": monetization_text(brief),
            "category": category,
            "keywords": [*terms[:3], "pricing", "policy", "retention"],
            "pain_points": [
                "Paid features need a clear value boundary.",
                "Subscription claims need careful copy and human review.",
            ],
            "competitor_gaps": [
                "Competitors often hide pricing until late in onboarding.",
                "Policy-sensitive domains need transparent disclaimers.",
            ],
            "evidence_json": {
                "iap_enabled": brief.get("iap_enabled", False),
                "subscription_enabled": brief.get("subscription_enabled", False),
                "ads_enabled": brief.get("ads_enabled", False),
            },
            "confidence_score": 64,
        },
    ]


def deterministic_candidates(brief: dict[str, Any], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = derive_focus_terms(brief)
    category = str(brief.get("target_category") or terms[0].title())
    title_seed = first_sentence(str(brief.get("title") or ""), f"{category} Companion")
    base_title = title_seed if len(title_seed) <= 54 else title_seed[:54].strip()
    raw_prompt = str(brief.get("raw_prompt") or brief.get("title") or "focused workflow")
    target_country = brief.get("target_country", "US")
    language = brief.get("target_language", "en")
    backend_mode = brief.get("backend_mode", "none")
    score_bonus = 8 if brief.get("subscription_enabled") or brief.get("iap_enabled") else 0
    backend_penalty = 8 if backend_mode not in {"none", "local"} else 0
    return [
        {
            "title": f"{base_title} Studio",
            "description": f"A focused {category.lower()} app that turns the user's first goal into a guided daily workflow with visible progress and privacy-aware defaults.",
            "target_user": f"Mobile users in {target_country} who want a practical {category.lower()} workflow in {language}.",
            "problem": first_sentence(raw_prompt, "The user needs a simpler way to turn intent into repeated action."),
            "unique_angle": "Start with one concrete user goal, then generate only the next useful action instead of a cluttered feature hub.",
            "core_features": [
                "Goal capture onboarding",
                "Daily action dashboard",
                "Progress and confidence status cards",
                "Local-first settings and export placeholder",
                "Human-review release checklist",
            ],
            "monetization_plan": monetization_text(brief),
            "iap_plan_json": {"enabled": bool(brief.get("iap_enabled")), "items": ["Advanced templates", "Export packs"]},
            "subscription_plan_json": {"enabled": bool(brief.get("subscription_enabled")), "tiers": ["Pro monthly", "Pro annual"]},
            "backend_plan_json": {"mode": backend_mode, "first_release": "local-first" if backend_mode == "none" else backend_mode},
            "opportunity_score": min(92, 74 + score_bonus - backend_penalty),
            "demand_score": 76,
            "pain_score": 78,
            "monetization_score": 72 + score_bonus,
            "build_feasibility_score": 84 - backend_penalty,
            "differentiation_score": 73,
            "policy_risk_score": 22,
            "originality_score": 81,
            "status": "proposed",
        },
        {
            "title": f"{category} Sprint Coach",
            "description": "A lightweight coach that creates short action sprints, reflection prompts, and a clean timeline for users who abandon heavier apps.",
            "target_user": "Users who already tried generic trackers but need a narrower guided routine.",
            "problem": "Generic productivity and learning tools create planning overhead before the user gets a useful action.",
            "unique_angle": "Compress planning into one short sprint loop: choose goal, do next action, reflect, repeat.",
            "core_features": [
                "Sprint setup",
                "Next-action queue",
                "Reflection log",
                "Progress streaks",
                "Privacy and export settings",
            ],
            "monetization_plan": monetization_text(brief),
            "iap_plan_json": {"enabled": bool(brief.get("iap_enabled")), "items": ["Sprint packs"]},
            "subscription_plan_json": {"enabled": bool(brief.get("subscription_enabled")), "tiers": ["Coach Plus"]},
            "backend_plan_json": {"mode": backend_mode},
            "opportunity_score": min(88, 69 + score_bonus),
            "demand_score": 72,
            "pain_score": 75,
            "monetization_score": 68 + score_bonus,
            "build_feasibility_score": 88 - backend_penalty,
            "differentiation_score": 68,
            "policy_risk_score": 18,
            "originality_score": 76,
            "status": "proposed",
        },
        {
            "title": f"{category} Field Notes",
            "description": "A note-to-action app that helps users capture friction, classify recurring pain points, and turn them into repeatable personal workflows.",
            "target_user": "Operators, learners, and creators who need structured field notes rather than a blank notes app.",
            "problem": "Useful observations get lost because capture tools do not convert notes into an executable plan.",
            "unique_angle": "Mine the user's own notes for recurring patterns, then suggest the next experiment.",
            "core_features": [
                "Structured capture",
                "Pattern tags",
                "Experiment planner",
                "Evidence timeline",
                "Review dashboard",
            ],
            "monetization_plan": "Best kept free-first until note retention is validated; add export packs later.",
            "iap_plan_json": {"enabled": bool(brief.get("iap_enabled")), "items": ["Export templates"]},
            "subscription_plan_json": {"enabled": False},
            "backend_plan_json": {"mode": "none"},
            "opportunity_score": 66,
            "demand_score": 65,
            "pain_score": 70,
            "monetization_score": 56,
            "build_feasibility_score": 90,
            "differentiation_score": 70,
            "policy_risk_score": 15,
            "originality_score": 78,
            "status": "proposed",
        },
    ]


class DeterministicResearchProvider:
    name = "deterministic_provider"

    def available(self) -> bool:
        return True

    def collect(self, brief: dict[str, Any]) -> list[dict[str, Any]]:
        return deterministic_findings(brief)

    def run(self, brief: dict[str, Any]) -> ResearchBundle:
        findings = self.collect(brief)
        candidates = deterministic_candidates(brief, findings)
        return ResearchBundle(
            findings=findings,
            candidates=candidates,
            evidence=[{"provider": self.name, "method": "brief_heuristics", "fallback": True}],
        )
