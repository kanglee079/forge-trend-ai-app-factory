from __future__ import annotations

import hashlib
from typing import Any


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.35))


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def summarize_context(text: str, *, limit: int = 1200) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    head = compact[: int(limit * 0.7)].rstrip()
    tail = compact[-int(limit * 0.3) :].lstrip()
    return f"{head}\n...\n{tail}"


def plan_context_pack(
    *,
    pack_type: str,
    text: str,
    important_files: list[str] | None = None,
    token_limit: int = 4000,
) -> dict[str, Any]:
    summary = summarize_context(text, limit=min(1800, max(600, token_limit // 2)))
    original_tokens = estimate_tokens(text)
    summary_tokens = estimate_tokens(summary)
    return {
        "pack_type": pack_type,
        "full_text_hash": text_hash(text),
        "summary": summary,
        "important_files": important_files or [],
        "token_estimate": summary_tokens,
        "decision": {
            "original_tokens_estimated": original_tokens,
            "summary_tokens_estimated": summary_tokens,
            "tokens_saved_estimated": max(0, original_tokens - summary_tokens),
            "token_limit": token_limit,
            "strategy": "use_summary" if original_tokens > token_limit else "use_full_context",
        },
    }


def skill_prompt_header(selected_skills: list[dict[str, Any]]) -> str:
    if not selected_skills:
        return "Selected skills: none"
    lines = ["Selected skills:"]
    for skill in selected_skills:
        lines.append(f"- {skill.get('slug')}: {skill.get('reason') or skill.get('category')}")
        for fragment in (skill.get("prompt_fragments") or [])[:2]:
            template = " ".join(str(fragment.get("prompt_template") or "").split())
            if template:
                lines.append(f"  Prompt fragment ({fragment.get('name')}): {template[:700]}")
    return "\n".join(lines)
