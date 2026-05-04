CALCULATOR_ARCHETYPE = {
    "id": "calculator",
    "screens": ["input form", "result breakdown", "history", "settings", "privacy"],
    "entities": ["CalculationInput", "CalculationResult", "HistoryItem"],
    "actions": ["Enter values", "Calculate result", "Save calculation", "Reset form"],
    "sample_data": [{"label": "Demo calculation", "value": 42}],
    "tests": ["input validates", "calculate button returns result", "history stores result"],
    "store_positioning": {"short_vi": "Tính toán nhanh, lưu lịch sử và rõ quyền riêng tư."},
    "quality_checks": ["has_input_flow", "has_result_state", "has_history"],
}
