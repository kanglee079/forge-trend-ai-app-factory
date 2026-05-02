# Policy Gates

The MVP policy agent checks:

- No copycat or trademark-adjacent naming.
- No hardcoded keys in Flutter source.
- No excessive Android permissions.
- No minimum-functionality issue.
- No webview-only app.
- Privacy policy placeholder exists.

Policy output shape:

```json
{
  "risk": "low",
  "passed": true,
  "issues": [],
  "required_changes": []
}
```

Projects that fail QA or high-risk policy checks are moved to `NEEDS_HUMAN_REVIEW`.
