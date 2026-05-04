from __future__ import annotations

from typing import Any

from .learning_memory import classify_failure
from .retrospective import human_review_reason


def autopilot_decision(state: str, reason: str, attempt: int, max_attempts: int) -> dict[str, Any]:
    should_retry = attempt < max_attempts and classify_failure(reason) not in {"provider_auth_missing", "budget_exceeded"}
    return {
        "state": state,
        "reason": reason,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "action": "retry_fix" if should_retry else "block_for_human_review",
        "taxonomy": classify_failure(reason),
    }


def build_run_evaluation(
    *,
    brief: dict[str, Any] | None,
    project: dict[str, Any],
    provider: str,
    archetype: str | None,
    final_status: str,
    qa_output: dict[str, Any] | None,
    policy_output: dict[str, Any] | None,
    quality_output: dict[str, Any] | None,
    elapsed_seconds: int,
    fix_iterations: int,
) -> dict[str, Any]:
    review_reason = human_review_reason(qa_output, policy_output, quality_output)
    return {
        "brief_id": (brief or {}).get("id"),
        "project_id": project.get("id"),
        "category": (brief or {}).get("target_category"),
        "language": (brief or {}).get("target_language"),
        "monetization": (brief or {}).get("monetization_mode"),
        "provider": provider,
        "archetype": archetype,
        "final_status": final_status,
        "qa_passed": bool(qa_output and qa_output.get("passed")),
        "quality_score": int((quality_output or {}).get("score") or 0),
        "policy_passed": bool(policy_output and policy_output.get("passed")),
        "store_readiness_score": int((quality_output or {}).get("store_readiness_score") or 0),
        "time_to_complete_seconds": elapsed_seconds,
        "fix_iterations": fix_iterations,
        "failure_reason": review_reason,
        "human_review_reason": review_reason if final_status != "release_candidate" else None,
        "metrics_json": {
            "quality": quality_output or {},
            "policy": policy_output or {},
            "qa_summary": {"passed": bool(qa_output and qa_output.get("passed"))},
        },
    }
