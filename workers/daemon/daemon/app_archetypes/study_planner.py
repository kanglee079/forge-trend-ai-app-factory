STUDY_PLANNER_ARCHETYPE = {
    "id": "study_planner",
    "screens": ["subject list", "deadline planner", "study session", "weekly progress", "settings"],
    "entities": ["Subject", "Deadline", "StudySession"],
    "actions": ["Add subject", "Plan session", "Complete session", "Review weekly progress"],
    "sample_data": [{"subject": "Toán", "deadline": "Tuần này"}],
    "tests": ["add subject", "complete session", "progress updates"],
    "store_positioning": {"short_vi": "Lập kế hoạch học tập và theo dõi tiến độ tuần."},
    "quality_checks": ["has_plan_action", "has_progress", "has_vietnamese_copy"],
}
