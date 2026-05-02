# ForgeTrend Product Recovery Plan

## Current assessment

ForgeTrend already has a useful technical skeleton: README documents a local desktop shell, dashboard, FastAPI API, Docker services, local Python worker daemon, Codex CLI integration, and Flutter Android debug build pipeline. However, the product experience is still closer to an internal engineering prototype than a usable app factory.

The main problem is not only visual polish. The larger problem is that the app does not clearly communicate:

- what the user must do first;
- whether the local machine is ready;
- whether API keys, worker, Codex, Flutter, Docker, Redis, and database are connected;
- what the pipeline is doing now;
- why a job failed;
- what file/artifact was produced;
- what to fix next;
- when an app is truly ready;
- what actions are dangerous and require confirmation.

This plan turns the repo back toward a usable local-first AI App Factory.

## Product direction

ForgeTrend should not be a simple CRUD dashboard. It should be a local control plane for an autonomous app-building pipeline.

Target product statement:

> ForgeTrend is a local-first AI App Factory dashboard that helps one machine or many machines discover app opportunities, generate original Flutter app projects, run coding agents, test/fix/build them, and show every step clearly until the app reaches release-candidate quality.

## Non-negotiable principles

1. Every async action must show loading or progress.
2. Every important action must show success/error feedback.
3. Every dangerous action must require confirmation.
4. Every long-running job must have a visible state machine.
5. Every failure must show cause, retry option, and copyable logs.
6. Every project must have a clear readiness score.
7. User must never wonder what to do next.
8. No production release automation without human approval.
9. No clone/copycat automation; only original, improved app concepts.
10. API keys and secrets must never appear in UI logs, generated code, or commits.

## Reference projects to learn from

### OpenHands

Useful lessons:

- separate SDK/CLI/Local GUI layers;
- local GUI for running agents on a laptop;
- REST API plus single-page React app;
- agent UX similar to Devin/Jules style;
- clear split between agent engine and UI.

Apply to ForgeTrend:

- keep worker/agent execution separate from dashboard;
- dashboard should be a live monitoring/control UI, not just forms;
- every pipeline event should be visible and traceable.

### Dyad

Useful lessons:

- local app builder positioning;
- BYOK model;
- cross-platform Mac/Windows emphasis;
- simple download-and-go user expectation.

Apply to ForgeTrend:

- first-run UX must be extremely clear;
- app should explain missing dependencies and setup steps;
- the dashboard must feel like a desktop app, not a raw localhost page.

### AutoGPT Platform

Useful lessons:

- agent builder, workflow management, deployment controls, monitoring, analytics;
- self-host setup must document Docker, Git, Node, npm, OS support;
- continuous agents need lifecycle controls.

Apply to ForgeTrend:

- add factory lifecycle controls: Start, Pause, Resume, Stop;
- add workflow step visualization;
- add run history, costs, failures, and retry limits.

### Aider

Useful lessons:

- maps the codebase;
- integrates with Git;
- can run lint/test after changes;
- keeps developer in control.

Apply to ForgeTrend:

- every agent code pass must create a git commit in project workspace;
- QA/fix loop must be visible;
- failed test output must feed into fix iterations;
- user must be able to inspect diffs/artifacts.

## Current gap analysis

| Area | Current state | Problem | Target state |
|---|---|---|---|
| Overview | Basic counts and latest projects | Does not show readiness or actionable next step | Command center with system health, setup checklist, recent failures, running jobs, cost, and readiness |
| App shell | Sidebar, top status, theme toggle | Good base but missing notification center and factory controls | Add Start/Pause/Resume/Stop, notification bell, global command/status area |
| API Keys | Add/list keys | No disable/delete/assign/test key, no cost telemetry | Full key manager with validation, budgets, assigned worker, masked-only display, test provider button |
| Workers | Shows capabilities | No environment doctor or install guidance | Worker readiness panel with missing dependency actions |
| Ideas | Manual idea CRUD | No trend research, no scoring evidence, no differentiation gate | Idea radar with opportunity score, originality risk, evidence, and approve/reject |
| Projects | Create/run | Run can be unclear/dangerous, weak progress preview | Project cards with pipeline progress, confirm run, stop/retry/delete controls |
| Project Detail | Tabs show raw data | No state machine, current step, elapsed time, retry count, copyable logs | Live pipeline console with timeline, progress, log filters, artifacts, QA, policy gates |
| Logs | Only per-project partial logs | No standalone logs page | Global logs viewer with search/filter/copy/clear/export |
| Settings | Placeholder only in project detail | No global settings | Global settings page: model, provider, retry limit, paths, budgets, notification, theme |
| Notifications | Toast provider exists | Not used consistently, no notification history | Toast + notification center + unread count |
| QA | Stored results | Not turned into readiness gates | QA dashboard with pass/fail, failed command details, retry/fix actions |
| Policy | Basic checklist | Too shallow for app-store safety | Originality, trademark, minimum functionality, permission, privacy, release blockers |

## Required information architecture

The dashboard navigation should become:

1. Overview
2. Setup Doctor
3. API Keys
4. Workers
5. Ideas / Trend Radar
6. Projects
7. Runs
8. Logs
9. Artifacts
10. Settings

Project detail should contain:

1. Summary
2. Pipeline
3. PRD
4. Design
5. Code Agent
6. QA
7. Policy
8. Artifacts
9. Logs
10. Settings

## Pipeline state machine

Every project must show this pipeline:

1. Environment Check
2. Trend / Idea Validation
3. Opportunity Scoring
4. PRD Generation
5. UX / Design System
6. Flutter Scaffold
7. Code Agent Pass
8. Build
9. Test
10. Auto Fix Loop
11. Policy Gate
12. Artifact Packaging
13. Release Candidate
14. Human Approval Required

Each step must support:

- pending
- running
- passed
- failed
- skipped
- needs_human_review

Each step must show:

- start time;
- end time;
- duration;
- retry count;
- latest message;
- link to logs;
- produced artifacts;
- action: retry, copy log, open artifact.

## P0 implementation tasks

These tasks are required before the app can be considered usable.

### P0.1 Overview command center

Add:

- system readiness score;
- setup checklist with actionable links;
- worker online/offline summary;
- key health summary;
- active/running project cards;
- recent failures;
- latest artifacts;
- cost/budget summary placeholder;
- Start/Pause Factory controls.

Acceptance criteria:

- New user can understand what to do next from Overview alone.
- Offline API/worker state is visible.
- Empty state includes CTA.
- Loading skeleton appears while data loads.
- Errors do not disappear into console only.

### P0.2 Project pipeline panel

Replace the simple overview cards with a real pipeline progress panel.

Acceptance criteria:

- Current step is obvious.
- Progress percent is calculated from step statuses.
- Failed step is visually obvious.
- Latest log is shown inline.
- Retry count and elapsed time are visible.
- User can copy error logs.

### P0.3 Run confirmation and job controls

Add confirmations and controls:

- Run pipeline confirmation if workspace exists.
- Stop current run.
- Retry failed step.
- Delete project confirmation.
- Clear logs confirmation.

Acceptance criteria:

- No workspace-modifying action runs without user confirmation.
- Button shows loading state while request is pending.
- Success/failure uses toast and visible notice.

### P0.4 API key manager completion

Add:

- client validation;
- provider test button;
- disable/enable key;
- delete key with confirm;
- assign key to worker;
- daily/monthly budget warning;
- never show full key after save.

Acceptance criteria:

- Invalid key/budget cannot be submitted.
- Duplicate key errors are clear.
- Deleting/disabling requires confirmation.
- All actions show toast feedback.

### P0.5 Logs viewer

Add `/logs` page.

Features:

- filter by project;
- filter by worker;
- filter by level;
- search;
- copy log;
- clear log with confirm;
- auto-refresh toggle;
- export JSON/text.

Acceptance criteria:

- User can debug failures without opening terminal.

### P0.6 Setup Doctor

Add `/doctor` page and API endpoint wrapping the existing doctor script.

Checks:

- Node/pnpm;
- Python/venv;
- Git;
- Docker;
- Redis;
- Postgres;
- MinIO;
- Flutter;
- Android SDK;
- Xcode on macOS;
- Codex CLI;
- Aider optional;
- worker heartbeat;
- API health.

Acceptance criteria:

- Missing dependency shows exact install guidance for macOS and Windows.
- Doctor results are saved and visible in worker readiness.

## P1 implementation tasks

### P1.1 Global Settings

Add `/settings` page:

- default model/provider;
- max fix iterations;
- workspace root;
- auto-refresh interval;
- notification preference;
- theme;
- budget limits;
- feature flags.

### P1.2 Notification center

Add:

- global notification bell;
- unread count;
- event history;
- job failed/completed notifications;
- worker offline notifications;
- budget warning notifications.

### P1.3 Idea Radar

Manual ideas are not enough. Add trend/research cards:

- source;
- evidence;
- user pain;
- competitor weakness;
- differentiation plan;
- originality risk;
- policy risk;
- approve/reject.

### P1.4 Artifact viewer

Artifacts should not only show local paths.

Add:

- artifact type icons;
- open folder/copy path;
- preview markdown docs;
- download link when MinIO is wired;
- generated APK visibility.

### P1.5 Release readiness gate

Add release gate checklist:

- QA passed;
- policy passed;
- no secret in source;
- privacy policy exists;
- minimum functionality passed;
- app name safe;
- icon/screenshots present;
- human approval required.

## P2 polish tasks

- Framer Motion or CSS transitions for page/card/button interactions.
- Better skeleton loaders.
- Empty-state illustrations/icons.
- Keyboard shortcuts.
- Command palette.
- Better mobile responsiveness.
- Demo mode with seeded data.

## Backend changes required

Add endpoints:

- `GET /doctor`
- `GET /runs`
- `POST /projects/{id}/stop`
- `POST /projects/{id}/retry`
- `DELETE /projects/{id}`
- `DELETE /projects/{id}/events`
- `GET /events`
- `PATCH /api-keys/{id}` for enable/disable/assign
- `DELETE /api-keys/{id}`
- `POST /api-keys/{id}/test`
- `GET /settings`
- `PATCH /settings`

## Frontend components required

Create shared components:

- `LoadingButton`
- `PageLoader`
- `DataState`
- `ConfirmDangerDialog`
- `PipelineStepper`
- `StepStatusIcon`
- `LogViewer`
- `CopyButton`
- `ReadinessCard`
- `SetupChecklist`
- `NotificationCenter`
- `FactoryControls`
- `ArtifactCard`
- `DoctorCheckCard`

## Definition of Done

The app is not complete until all of these pass:

- App starts on macOS using `run.command`.
- App starts on Windows using `run.bat`.
- Overview explains exact next step for first-time user.
- API key create/disable/delete/test flows have validation, loading, confirm, and toast.
- Worker page shows missing dependency guidance.
- Project run requires confirmation.
- Project detail shows pipeline state machine.
- Logs page supports search/filter/copy.
- Settings page exists.
- Setup Doctor exists.
- QA failures are visible and copyable.
- Policy failures block release candidate status.
- Generated project has PRD, design docs, Flutter app, QA results, policy results, and artifacts.
- No async action fails silently.
- No dangerous action runs without confirmation.
- `pnpm lint` passes.
- `pnpm build` passes.
- `pnpm doctor` produces a readable report.

## Recommended implementation order

1. Add backend endpoints for project events/logs, delete/clear/stop/retry, API key actions.
2. Add shared frontend components listed above.
3. Rebuild Overview as command center.
4. Rebuild Project Detail around `PipelineStepper`.
5. Add standalone Logs page.
6. Add Setup Doctor page.
7. Upgrade API Keys and Workers pages.
8. Add Settings and Notification Center.
9. Add Idea Radar improvements.
10. Add tests and smoke checks.

## Final note

The project should stop trying to look like a small admin CRUD app. It must become a live operations cockpit for an AI software factory. The user should always see: what is ready, what is running, what failed, what to do next, and whether the generated app is safe to release.
