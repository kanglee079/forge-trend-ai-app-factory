# Security

## Secrets

- API keys are encrypted at rest with `FACTORY_SECRET_KEY`.
- `.env` is ignored by git.
- API responses return only `key_hint`; plaintext keys are never returned.
- Worker command execution removes common provider API key environment variables by default.
- The Codex CLI adapter is a narrow exception: it can preserve local Codex/OpenAI auth only for the `codex exec` process because Codex is the configured machine-local coding provider.
- Logs are redacted before storage.

## Key rotation

1. Add the replacement key in the dashboard.
2. Disable the old key using the key status field.
3. Confirm no active worker is assigned to the old key.
4. Delete or archive the old key out of band if your retention policy requires it.

## Budgets

Each key has daily and monthly budget fields. Dashboard-stored keys are encrypted metadata in this MVP. Codex CLI uses local machine auth, so budget enforcement for Codex must be added at the provider adapter layer before unattended production use.

## Production publishing

Production publishing is intentionally not implemented in MVP. Human approval must be added before any release automation can publish to app stores.
