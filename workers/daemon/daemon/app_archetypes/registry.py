from __future__ import annotations

from typing import Any

from .checklist import CHECKLIST_ARCHETYPE
from .calculator import CALCULATOR_ARCHETYPE
from .content_tool import CONTENT_TOOL_ARCHETYPE
from .ai_content_tool import AI_CONTENT_TOOL_ARCHETYPE
from .education import EDUCATION_ARCHETYPE
from .expense_tracker import EXPENSE_TRACKER_ARCHETYPE
from .finance_basic import FINANCE_BASIC_ARCHETYPE
from .habit_tracker import HABIT_TRACKER_ARCHETYPE
from .inventory_tracker import INVENTORY_TRACKER_ARCHETYPE
from .productivity import PRODUCTIVITY_ARCHETYPE
from .study_planner import STUDY_PLANNER_ARCHETYPE
from .utility import UTILITY_ARCHETYPE

ARCHETYPES: dict[str, dict[str, Any]] = {
    item["id"]: item
    for item in [
        EDUCATION_ARCHETYPE,
        PRODUCTIVITY_ARCHETYPE,
        UTILITY_ARCHETYPE,
        HABIT_TRACKER_ARCHETYPE,
        CHECKLIST_ARCHETYPE,
        CALCULATOR_ARCHETYPE,
        CONTENT_TOOL_ARCHETYPE,
        AI_CONTENT_TOOL_ARCHETYPE,
        FINANCE_BASIC_ARCHETYPE,
        EXPENSE_TRACKER_ARCHETYPE,
        INVENTORY_TRACKER_ARCHETYPE,
        STUDY_PLANNER_ARCHETYPE,
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
    if "calculator" in text or "tính toán" in text:
        return CALCULATOR_ARCHETYPE
    if "expense" in text or "chi tiêu" in text:
        return EXPENSE_TRACKER_ARCHETYPE
    if "inventory" in text or "tồn kho" in text or "bán hàng online" in text:
        return INVENTORY_TRACKER_ARCHETYPE
    if "student" in text or "study planner" in text or "sinh viên" in text:
        return STUDY_PLANNER_ARCHETYPE
    if "finance" in text or "budget" in text or "tài chính" in text:
        return FINANCE_BASIC_ARCHETYPE
    if "ai content" in text or "nội dung ai" in text:
        return AI_CONTENT_TOOL_ARCHETYPE
    if "content" in text or "write" in text or "nội dung" in text:
        return CONTENT_TOOL_ARCHETYPE
    if "productivity" in text or "task" in text or "năng suất" in text:
        return PRODUCTIVITY_ARCHETYPE
    return UTILITY_ARCHETYPE
