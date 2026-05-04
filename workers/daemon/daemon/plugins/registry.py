PLUGINS = [
    {"id": "deterministic_research", "name": "Deterministic Research", "type": "research_provider", "enabled": True, "capabilities": ["offline_evidence"], "config_schema": {}},
    {"id": "web_research", "name": "Web Research", "type": "research_provider", "enabled": True, "capabilities": ["allowlisted_urls"], "config_schema": {"allowed_urls": "string"}},
    {"id": "codex_cli", "name": "Codex CLI", "type": "code_provider", "enabled": True, "capabilities": ["code_pass", "repair_loop"], "config_schema": {"timeout_seconds": "integer"}},
    {"id": "app_archetypes", "name": "App Archetypes", "type": "app_archetype", "enabled": True, "capabilities": ["education", "productivity", "habit_tracker", "checklist", "calculator", "expense_tracker", "ai_content_tool", "inventory_tracker", "study_planner"], "config_schema": {}},
    {"id": "product_quality_gate", "name": "Product Quality Gate", "type": "quality_gate", "enabled": True, "capabilities": ["journey_gate", "aso_gate", "banned_copy"], "config_schema": {"threshold": "integer"}},
    {"id": "store_assets", "name": "Store Asset Generator", "type": "store_asset_generator", "enabled": True, "capabilities": ["listing_drafts", "screenshot_plan"], "config_schema": {}},
]
