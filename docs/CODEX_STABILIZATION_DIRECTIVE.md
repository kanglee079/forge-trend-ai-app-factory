# Codex Stabilization Directive

This file is the implementation directive for Codex. The user acts as Product Planner and Reviewer. Codex acts as Implementer. The goal is to make ForgeTrend actually runnable and usable as a local-first AI App Factory.

## Role split

### Human / ChatGPT Planner

- Define product direction.
- Prioritize issues.
- Review PRs and runtime evidence.
- Approve release-candidate quality.

### Codex Implementer

- Read this directive before coding.
- Fix tasks in priority order.
- Run verification commands after each change.
- Commit small, reversible changes.
- Never hide failures.
- Never mark a task done without runtime evidence.

## Current stability verdict

The project has improved UI and workflow pieces, but it should not be considered stable until the P0 checklist below passes on a clean machine.

Known strengths:

- Desktop launcher exists for macOS and Windows.
- Dashboard, API, Docker Compose, worker daemon, Redis queue, and Flutter output pipeline exist.
- Command Center exists.
- PipelineStepper exists.
- Logs page exists.
- Doctor page exists.
- API key manager has test/disable/delete actions.

Known blockers:

1. Database model/migration mismatch: `ApiKey.key_fingerprint` exists in the SQLAlchemy model and API logic, but the initial Alembic migration does not create this column. Fresh DB setup can break API key list/create flows.
2. `AppSettings` and `FactoryState` schemas exist, but there are no real settings/factory-state endpoints or UI page yet.
3. Factory controls in the dashboard are currently local UI state only; they do not control the daemon.
4. Stop pipeline only marks `stop_requested`; the worker daemon does not yet cancel between steps.
5. Windows launcher path handling should use `fileURLToPath(import.meta.url)` instead of raw URL pathname.
6. Doctor uses `python3` for Python detection, which can fail on Windows even when `python` or `py` is installed.
7. Artifact viewing is still mostly local paths; no preview/download/open/copy UX is complete.
8. No smoke test proves a clean machine can run setup, migrate, start API/dashboard/worker, create key, create idea, create project, run pipeline, and inspect logs.

## P0: Must fix before claiming “runs correctly”

### P0.1 Fix DB migration mismatch

Add a new Alembic migration or update the initial migration before release if history can be rewritten.

Required DB changes:

- Add `api_keys.key_fingerprint VARCHAR(64) NOT NULL`.
- Backfill for existing rows if needed.
- Add unique constraint: provider + key_fingerprint.
- Ensure `db:migrate` works from a clean Postgres volume.

Acceptance checks:

```bash
rm -rf .runtime || true
docker compose down -v
docker compose up -d postgres redis minio
pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py
pnpm db:migrate
pnpm dev:api
curl http://localhost:8000/api-keys
```

Expected: `[]`, not a database column error.

### P0.2 Fix root build order and build verification

Change root build script to build shared before dashboard.

Suggested:

```json
"build": "pnpm --filter @forge/shared build && pnpm --filter @forge/dashboard build"
```

Acceptance checks:

```bash
pnpm install --frozen-lockfile=false
pnpm build
pnpm lint
```

### P0.3 Harden Windows/macOS launcher

Update `scripts/run_desktop.mjs`:

- Use `fileURLToPath(import.meta.url)` and `dirname` to compute paths safely.
- Use cross-platform command resolution for `pnpm`, `docker`, and `node` on Windows.
- Show readable error if Node, pnpm, Docker, or Python is missing.
- Write a launcher summary to `logs/launcher.log`.

Acceptance checks:

- `run.command` works on macOS.
- `run.bat` works on Windows.
- Missing Docker gives friendly message, not a raw stack trace.

### P0.4 Make Settings real

Implement:

- `GET /settings`
- `PATCH /settings`
- `GET /factory-state`
- `PATCH /factory-state`
- `apps/dashboard/app/settings/page.tsx`

Initial persistence can be `.runtime/settings.json` and `.runtime/factory_state.json` before DB persistence.

Settings fields:

- default_provider
- default_model
- max_fix_iterations
- workspace_root
- auto_refresh_seconds
- notifications_enabled
- theme
- daily_budget_usd
- monthly_budget_usd
- feature_flags

Acceptance checks:

- Settings page loads.
- User edits max fix iterations and refreshes page; value persists.
- Factory state persists after refresh.

### P0.5 Wire factory controls to backend

Overview Start/Pause/Stop must call real backend state, not local state only.

Required behavior:

- Start: factory mode becomes `running`; worker may consume queue.
- Pause: factory mode becomes `paused`; new jobs should not be consumed.
- Stop: factory mode becomes `stopped`; queued jobs should not be consumed and running projects should become stop requested.

Acceptance checks:

- Overview controls call backend.
- UI state persists after refresh.
- Worker reads factory mode before claiming a new Redis job.

### P0.6 Make stop cancellation real enough

Worker should check project status/factory mode between every pipeline step.

Required:

- Add helper `should_stop(project_id)` in worker API client.
- Check before PRD, UX, Code, QA, Fix, Policy.
- If stop requested, write event and set status `NEEDS_HUMAN_REVIEW` or `stopped`.

Acceptance checks:

- Start a project.
- Click Stop.
- Worker stops before next major step.
- Project detail shows stop event.

### P0.7 Add smoke test

Create `scripts/smoke_test.mjs` or `scripts/smoke_test.py`.

Smoke test should verify:

1. API health.
2. Doctor endpoint.
3. DB migration was applied.
4. API keys endpoint works.
5. Ideas endpoint works.
6. Projects endpoint works.
7. Events endpoint works.
8. Dashboard build exists or Next build passes.

Acceptance checks:

```bash
pnpm smoke
```

Expected: green summary with actionable failed checks.

## P1: Product completion after stability

### P1.1 Notification Center

Add a global notification bell with unread count and history.

Events to notify:

- worker offline
- API key test failed
- project queued
- project failed
- project release candidate
- policy high risk
- budget warning

### P1.2 Artifact viewer

Improve artifacts:

- copy path
- open folder instruction
- markdown preview for PRD/design docs
- APK path highlight
- future MinIO download link placeholder

### P1.3 Release readiness gate

Add release checklist:

- QA passed
- policy passed
- no secret markers
- privacy policy exists
- minimum functionality passed
- generated APK exists
- human approval required

### P1.4 Idea Radar

Move from manual idea CRUD to evidence-backed idea cards.

Add fields or evidence JSON UI:

- source
- competitor weakness
- user pain
- differentiation angle
- originality risk
- policy risk
- approve/reject

## Verification protocol for Codex

After every P0 task, run as much of this as possible:

```bash
pnpm install --frozen-lockfile=false
pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm lint
pnpm build
pnpm doctor
```

If a command fails, Codex must:

1. Capture the exact error.
2. Fix the root cause.
3. Re-run the failed command.
4. Add notes to `docs/STABILITY_REPORT.md`.

## Required report

Create/update `docs/STABILITY_REPORT.md` with:

- date/time
- OS tested
- commands run
- pass/fail result
- known remaining risks
- screenshots optional

## Do not do yet

- Do not add production publishing automation.
- Do not add store account automation.
- Do not add app cloning logic.
- Do not expose full API keys.
- Do not log secrets.
- Do not mark local UI-only controls as complete.

## Completion definition

The project can be called “stable MVP” only when:

- Fresh DB migration works.
- API starts.
- Dashboard builds.
- Worker starts.
- Doctor works.
- Settings persist.
- Factory controls persist and affect worker behavior.
- Project run/retry/stop has visible feedback.
- Logs are searchable and copyable.
- Smoke test passes.
- Stability report exists.
