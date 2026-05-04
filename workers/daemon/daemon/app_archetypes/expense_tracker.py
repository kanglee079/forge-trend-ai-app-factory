EXPENSE_TRACKER_ARCHETYPE = {
    "id": "expense_tracker",
    "screens": ["expense input", "monthly summary", "category history", "budget warning", "settings"],
    "entities": ["Expense", "Category", "Budget"],
    "actions": ["Add expense", "Edit category", "Review monthly total", "Clear demo data"],
    "sample_data": [{"category": "Ăn uống", "amount": 120000}],
    "tests": ["add expense", "summary updates", "history shows expense"],
    "store_positioning": {"short_vi": "Theo dõi chi tiêu cá nhân bằng luồng local-first đơn giản."},
    "quality_checks": ["has_add_action", "has_summary", "has_privacy_copy"],
}
