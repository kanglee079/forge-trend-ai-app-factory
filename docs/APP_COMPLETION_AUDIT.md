# App Completion Audit

Status legend: Todo, In Progress, Done.

| Area | Issue | Severity | Handling | Files / Modules | Status |
| --- | --- | --- | --- | --- | --- |
| App shell | Sidebar-only layout lacks top system status, active navigation, first-run guidance, and theme control. | High | Add app shell with top bar, live API/worker indicators, active nav, and theme toggle. | `apps/dashboard/app/layout.tsx`, `apps/dashboard/components/AppShell.tsx` | Done |
| Design system | UI primitives are thin; no shared toast, confirm dialog, skeleton, progress, or robust empty/error state. | High | Expand reusable components and feedback provider. | `apps/dashboard/components/ui.tsx`, `apps/dashboard/components/feedback.tsx` | Done |
| Overview | Dashboard shows counts but not readiness, recent failures, onboarding, running jobs, or progress. | High | Add readiness checklist, system health, recent jobs/errors, and progress cards. | `apps/dashboard/app/page.tsx` | Done |
| API Keys | Create flow has partial feedback but no validation details, no confirm for disabling/removing, and weak empty state. | High | Add validation, toast, confirm disable, copy-safe masked state, and empty CTA. | `apps/dashboard/app/api-keys/page.tsx` | Done |
| Workers | Worker list needs live refresh, readiness state, and actionable offline guidance. | High | Convert to client page with auto-refresh, empty/error states, and ready-worker notice. | `apps/dashboard/app/workers/page.tsx` | Done |
| Ideas | Create flow needs validation, toast, loading, and guided empty state. | Medium | Add client validation, loading, toast/notice, and empty CTA. | `apps/dashboard/app/ideas/page.tsx` | In Progress |
| Projects | Run action can overwrite generated workspace and lacks confirm/progress; no delete action. | Critical | Add ready-worker guard, confirm run/delete, row loading, progress preview, and delete endpoint. | `apps/dashboard/app/projects/page.tsx`, `services/api/app/main.py` | Done |
| Project detail | Progress is split across tabs; no clear current step, retry count, elapsed time, log controls, or copy errors. | Critical | Add pipeline progress panel, current step, latest log, filtered logs, copy buttons, clear logs confirm. | `apps/dashboard/app/projects/[id]/ProjectDetailClient.tsx` | Done |
| Logs | No standalone log viewer with search/filter/copy/clear. | High | Add `/logs` page and project event clear endpoint. | `apps/dashboard/app/logs/page.tsx`, `services/api/app/main.py` | Done |
| Setup Doctor | Users cannot diagnose missing local dependencies from the UI. | Critical | Add `/doctor` page and API endpoint for tool, service, worker, Flutter, and Codex checks. | `apps/dashboard/app/doctor/page.tsx`, `services/api/app/main.py` | Done |
| Settings | No settings screen for local worker/model/retry/theme/notifications. | High | Add `/settings` page backed by API-persisted runtime settings for app preferences and worker retry limits. | `apps/dashboard/app/settings/page.tsx`, `services/api/app/runtime_state.py` | Done |
| Notification Center | Toasts disappear and there is no notification history or unread count. | Medium | Add shell notification bell backed by feedback provider history. | `apps/dashboard/components/NotificationCenter.tsx`, `apps/dashboard/components/feedback.tsx` | Done |
| Factory Controls | Start/Pause/Stop are local UI state and do not affect workers. | High | Persist factory mode through API and have workers pause/stop taking new jobs. | `apps/dashboard/app/page.tsx`, `services/api/app/main.py`, `workers/daemon/daemon/main.py` | Done |
| Worker Stop | Stop request does not interrupt the pipeline between agent steps. | High | Worker checks factory/project stop state between agent runs and marks project stopped. | `workers/daemon/daemon/agents.py`, `workers/daemon/daemon/api.py` | Done |
| Safety | Policy gate exists only inside project detail and lacks release blocking explanation. | Medium | Improve project policy panel and overview readiness gates. | `ProjectDetailClient.tsx`, `docs/POLICY_GATES.md` | In Progress |
| Forms | Server/client validation is inconsistent; slugs, labels, budgets, and descriptions need constraints. | High | Add Pydantic and client validation with friendly errors. | `services/api/app/schemas.py`, client pages | Todo |
| Async behavior | Several loads still fall back to `console.error` or silent failure. | High | Surface errors through toast/notice and retry controls. | All client pages | In Progress |
| Desktop launcher | Desktop shell exists, but README should clearly explain it is the primary entrypoint and localhost is internal. | Medium | Update README and launcher safeguards. | `README.md`, `run.command`, `run.bat`, `scripts/run_desktop.mjs` | Done |
| Demo data | No demo mode for empty or offline development. | Low | Add dev-only demo fallback or guided empty states. | `apps/dashboard/lib/demo.ts`, pages | Todo |
| Tests | No app-level smoke test for UI/API readiness or state logic. | High | Add smoke verification script and document QA checklist. | `scripts/app_smoke_test.mjs`, `docs/QA_CHECKLIST.md` | Todo |

## Current Screens

- Overview command center
- Setup Doctor
- API Keys
- Workers
- Ideas
- Projects
- Logs
- Settings
- Project detail with Overview, PRD, Agent Timeline, Logs, QA, Policy, Artifacts, Settings tabs

## Key UX Risks

- Trend/review mining is still mostly placeholder and does not yet produce evidence-backed ideas.
- Pipeline step state is inferred from events/artifacts/QA rather than a first-class DB table.
- Provider key testing validates decryptability locally but does not yet call provider APIs.
- Worker records can become stale; the API now marks stale workers offline, but the UI needs guidance.
- Artifact delivery still depends on local paths; MinIO links and previews remain incomplete.

## Completion Strategy

1. Add shared feedback and app shell primitives first.
2. Upgrade each screen to use those primitives.
3. Add missing API endpoints only where needed for production UX: disable key, delete project, clear project logs.
4. Add progress calculation and log viewer.
5. Add settings and onboarding.
6. Validate with build and smoke checks.
