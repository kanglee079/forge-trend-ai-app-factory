# Plugin System

ForgeTrend plugins describe replaceable capabilities without rewriting the core runtime.

Plugin categories:

- `research_provider`
- `idea_scorer`
- `app_archetype`
- `code_provider`
- `qa_runner`
- `quality_gate`
- `store_asset_generator`
- `report_generator`

Each plugin uses:

```json
{
  "id": "",
  "name": "",
  "type": "",
  "enabled": true,
  "capabilities": [],
  "config_schema": {}
}
```

The first registry lives in `workers/daemon/daemon/plugins/registry.py`. The next version should expose this through the API so the dashboard can test and configure plugins.
