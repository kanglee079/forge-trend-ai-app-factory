AI_CONTENT_TOOL_ARCHETYPE = {
    "id": "ai_content_tool",
    "screens": ["brief input", "draft list", "editor", "revision history", "export placeholder"],
    "entities": ["ContentBrief", "Draft", "Revision"],
    "actions": ["Create brief", "Generate draft placeholder", "Edit draft", "Save revision"],
    "sample_data": [{"brief": "Bài đăng giới thiệu sản phẩm mới", "channel": "Facebook"}],
    "tests": ["brief form works", "draft can be edited", "history records revision"],
    "store_positioning": {"short_vi": "Biến brief bán hàng thành draft nội dung có thể chỉnh sửa."},
    "quality_checks": ["no_fake_ai_claim", "has_editor", "has_history"],
}
