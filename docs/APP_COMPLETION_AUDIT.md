# App Completion Audit

Status legend: Todo, In Progress, Done.

| Area | Issue | Severity | Handling | Files / Modules | Status |
| --- | --- | --- | --- | --- | --- |
| App shell | Sidebar-only layout lacks top system status, active navigation, first-run guidance, and theme control. | High | Add app shell with top bar, live API/worker indicators, active nav, and theme toggle. | `apps/dashboard/app/layout.tsx`, `apps/dashboard/components/AppShell.tsx` | Done |
| Design system | UI primitives are thin; no shared toast, confirm dialog, skeleton, progress, or robust empty/error state. | High | Expand reusable components and feedback provider. | `apps/dashboard/components/ui.tsx`, `apps/dashboard/components/feedback.tsx` | Done |
| Overview | Dashboard shows counts but not readiness, recent failures, onboarding, running jobs, or progress. | High | Add readiness checklist, system health, recent jobs/errors, and progress cards. | `apps/dashboard/app/page.tsx` | Todo |
| API Keys | Create flow has partial feedback but no validation details, no confirm for disabling/removing, and weak empty state. | High | Add validation, toast, confirm disable, copy-safe masked state, and empty CTA. | `apps/dashboard/app/api-keys/page.tsx` | Todo |
| Workers | Worker list needs live refresh, readiness state, and actionable offline guidance. | High | Convert to client page with auto-refresh, empty/error states, and ready-worker notice. | `apps/dashboard/app/workers/page.tsx` | Done |
| Ideas | Create flow needs validation, toast, loading, and guided empty state. | Medium | Add client validation, loading, toast/notice, and empty CTA. | `apps/dashboard/app/ideas/page.tsx` | In Progress |
| Projects | Run action can overwrite generated workspace and lacks confirm/progress; no delete action. | Critical | Add ready-worker guard, confirm run/delete, row loading, progress preview, and delete endpoint. | `apps/dashboard/app/projects/page.tsx`, `services/api/app/main.py` | Todo |
| Project detail | Progress is split across tabs; no clear current step, retry count, elapsed time, log controls, or copy errors. | Critical | Add pipeline progress panel, current step, latest log, filtered logs, copy buttons, clear logs confirm. | `apps/dashboard/app/projects/[id]/ProjectDetailClient.tsx` | Todo |
| Logs | No standalone log viewer with search/filter/copy/clear. | High | Add `/logs` page and project event clear endpoint. | `apps/dashboard/app/logs/page.tsx`, `services/api/app/main.py` | Todo |
| Settings | No settings screen for local worker/model/retry/theme/notifications. | High | Add `/settings` page backed by localStorage for app preferences. | `apps/dashboard/app/settings/page.tsx` | Todo |
| Safety | Policy gate exists only inside project detail and lacks release blocking explanation. | Medium | Improve project policy panel and overview readiness gates. | `ProjectDetailClient.tsx`, `docs/POLICY_GATES.md` | Todo |
| Forms | Server/client validation is inconsistent; slugs, labels, budgets, and descriptions need constraints. | High | Add Pydantic and client validation with friendly errors. | `services/api/app/schemas.py`, client pages | Todo |
| Async behavior | Several loads still fall back to `console.error` or silent failure. | High | Surface errors through toast/notice and retry controls. | All client pages | In Progress |
| Desktop launcher | Desktop shell exists, but README should clearly explain it is the primary entrypoint and localhost is internal. | Medium | Update README and launcher safeguards. | `README.md`, `run.command`, `run.bat`, `scripts/run_desktop.mjs` | Done |
| Demo data | No demo mode for empty or offline development. | Low | Add dev-only demo fallback or guided empty states. | `apps/dashboard/lib/demo.ts`, pages | Todo |
| Tests | No app-level smoke test for UI/API readiness or state logic. | High | Add smoke verification script and document QA checklist. | `scripts/app_smoke_test.mjs`, `docs/QA_CHECKLIST.md` | Todo |

## Current Screens

- Overview
- API Keys
- Workers
- Ideas
- Projects
- Project detail with Overview, PRD, Agent Timeline, Logs, QA, Policy, Artifacts, Settings tabs

## Key UX Risks

- New users do not know the required sequence: Codex login, local worker, API key, idea, project, run pipeline.
- Running a project can modify workspace files but currently does not clearly ask for confirmation.
- Pipeline progress is not summarized as a state machine; users must infer from events.
- Worker records can become stale; the API now marks stale workers offline, but the UI needs guidance.
- Logs exist per project but are not searchable or easy to copy.

## Completion Strategy

1. Add shared feedback and app shell primitives first.
2. Upgrade each screen to use those primitives.
3. Add missing API endpoints only where needed for production UX: disable key, delete project, clear project logs.
4. Add progress calculation and log viewer.
5. Add settings and onboarding.
6. Validate with build and smoke checks.
