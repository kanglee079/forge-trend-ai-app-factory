from __future__ import annotations

from typing import Any

from .checklist import CHECKLIST_ARCHETYPE
from .content_tool import CONTENT_TOOL_ARCHETYPE
from .education import EDUCATION_ARCHETYPE
from .finance_basic import FINANCE_BASIC_ARCHETYPE
from .habit_tracker import HABIT_TRACKER_ARCHETYPE
from .productivity import PRODUCTIVITY_ARCHETYPE
from .utility import UTILITY_ARCHETYPE

ARCHETYPES: dict[str, dict[str, Any]] = {
    item["id"]: item
    for item in [
        EDUCATION_ARCHETYPE,
        PRODUCTIVITY_ARCHETYPE,
        UTILITY_ARCHETYPE,
        HABIT_TRACKER_ARCHETYPE,
        CHECKLIST_ARCHETYPE,
        CONTENT_TOOL_ARCHETYPE,
        FINANCE_BASIC_ARCHETYPE,
    ]
}


def choose_archetype(category: str | None, prompt: str) -> dict[str, Any]:
    text = f"{category or ''} {prompt}".lower()
    if "hsk" in text or "learn" in text or "education" in text or "học" in text:
        return EDUCATION_ARCHETYPE
    if "habit" in text or "streak" in text or "thói quen" in text:
        return HABIT_TRACKER_ARCHETYPE
    if "checklist" in text or "kiểm tra" in text:
        return CHECKLIST_ARCHETYPE
    if "finance" in text or "budget" in text or "tài chính" in text:
        return FINANCE_BASIC_ARCHETYPE
    if "content" in text or "write" in text or "nội dung" in text:
        return CONTENT_TOOL_ARCHETYPE
    if "productivity" in text or "task" in text or "năng suất" in text:
        return PRODUCTIVITY_ARCHETYPE
    return UTILITY_ARCHETYPE
