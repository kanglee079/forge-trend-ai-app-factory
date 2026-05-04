# ForgeTrend AI App Factory

ForgeTrend is a local-first, Vietnamese-first AI App Factory for generating original Flutter app candidates from human-entered ideas. Start with [README.vi.md](README.vi.md) for the normal user flow, or [README.en.md](README.en.md) for the English guide.

The default product path is now Simple Mode: open the dashboard, choose **Tạo app từ ý tưởng của tôi**, review progress, then open APK/source/report artifacts. Advanced concepts like worker, Codex, deterministic mode, ports, queue, Docker, and diagnostics remain available in Advanced Mode.

ForgeTrend is intentionally not a clone factory and does not auto-publish apps. The pipeline creates PRD, UX notes, app blueprint, Flutter source, QA/build results, policy checks, product quality reports, store asset drafts, and human-review gates that block copycat, thin, generic, or secret-leaking apps.

## What runs

- Desktop shell: open `run.command` on macOS or `run.bat` on Windows
- Dashboard engine: `http://localhost:3000`
- API: `http://localhost:8000`
- PostgreSQL + pgvector, Redis, and MinIO via Docker Compose
- Python worker daemon with heartbeat, Redis polling, PRD/UX/code/QA/policy agents
- Local Codex CLI code agent integration for scaffold customization and QA fix passes
- Flutter Android debug build pipeline

## How to run on macOS

Double-click `run.command`, or run:

```bash
./run.command
```

This starts the local services, worker, dashboard engine, and opens the desktop app window.

Manual developer mode:

```bash
pnpm install
pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
```

Clean local reset when ports or services are stale:

```bash
pnpm reset:local
codex login
pnpm dev
pnpm e2e:factory
```

`pnpm reset:local` stops stale dashboard/API/worker processes on ports `3000` and `8000`, starts Postgres/Redis/MinIO, and runs migrations. It preserves generated workspaces unless you explicitly run with `RESET_WORKSPACES=true`.

Open `http://localhost:3000` only if you want the browser view; the normal app entry is `run.command`.

To run API and dashboard in Docker after setup:

```bash
docker compose up -d api dashboard
```

Run the worker locally for Flutter/Android QA and local Codex control:

```bash
codex login
pnpm dev:worker
```

Important: dashboard API keys are encrypted stored provider keys for future direct-provider/budget modes. The current Codex code agent uses the worker machine's local Codex CLI authentication, so `codex login` is still required on that machine.

The Docker worker is behind the optional `worker` Compose profile because it cannot see the host machine's Flutter SDK, Android SDK, or Codex login by default:

```bash
docker compose --profile worker up -d worker-daemon
```

For a full machine bootstrap:

```bash
chmod +x scripts/bootstrap_mac.sh scripts/start_dev.sh scripts/doctor.py
./scripts/bootstrap_mac.sh
```

## How to run on Windows

Double-click `run.bat`, or run PowerShell as a normal user:

```powershell
.\run.bat
```

Manual developer mode:

```powershell
pnpm install
pnpm setup:python
.\.venv\Scripts\python.exe scripts\ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
```

For a full bootstrap:

```powershell
.\scripts\bootstrap_windows.ps1
```

Windows supports Android builds. Use WSL2 for more stable Unix-style coding CLI workflows.

## Typical workflow

1. Open `run.command` or `run.bat`.
2. Run `pnpm doctor:ports` if anything returns 404 unexpectedly.
3. Log in to Codex CLI on the worker machine with `codex login`.
4. Start the worker with `pnpm dev:worker` if it is not already running.
5. Open `Factory`, enter a Factory Brief, and click `Start`.
6. Watch the Factory timeline for queued, worker picked, research, candidates, project created, and pipeline queued.
7. Open the linked project and watch Research, Tasks, Code Agent, QA, Policy, and Artifacts.

For an automated proof run:

```bash
pnpm e2e:factory
```

The E2E script creates a brief, starts it, waits for findings/candidates/project selection, waits for the project to finish in `release_candidate` or `NEEDS_HUMAN_REVIEW`, then prints tasks, logs, QA, policy, and artifacts. If it fails, the last project events and QA stderr are printed so you can see the exact broken step.

## Stale port checks

The dashboard defaults to `http://localhost:8000`. If an older API process is still bound to port `8000`, the UI can show 404s for new routes such as `/factory-briefs` even though the source code is correct.

```bash
pnpm doctor:ports
```

This prints port ownership, PID/command where possible, and detects a stale API when `/health` works but `/settings`, `/factory-briefs`, or `/events` return 404.

## API

Public MVP routes:

- `GET /health`
- `POST /api-keys`, `GET /api-keys`, `PATCH /api-keys/{id}`
- `POST /workers/register`, `POST /workers/{id}/heartbeat`, `GET /workers`
- `POST /ideas`, `GET /ideas`
- `POST /projects`, `GET /projects`, `GET /projects/{id}`
- `POST /projects/{id}/run-pipeline`
- `POST /factory-briefs`, `GET /factory-briefs`, `GET /factory-briefs/{id}`
- `POST /factory-briefs/{id}/start`, `POST /factory-briefs/{id}/finalize`
- `GET /factory-briefs/{id}/events`, `GET /factory-briefs/{id}/findings`, `GET /factory-briefs/{id}/candidates`
- `GET /projects/{id}/tasks`, `POST /projects/{id}/tasks/{task_id}/run`
- `GET /notifications`, `POST /notifications/read-all`
- `GET /projects/{id}/events`
- `GET /projects/{id}/qa`
- `GET /projects/{id}/policy`
- `GET /projects/{id}/artifacts`

The worker also uses `/internal/*` endpoints to write events and results.

## Known limitations

- Auto trend mode has a provider boundary and deterministic fallback. Optional low-volume web evidence can be enabled with `RESEARCH_ALLOWED_URLS` and `RESEARCH_ALLOWED_DOMAINS`; broad market connectors for app stores, Reddit, and Product Hunt are still future work.
- Codex CLI is wired for code customization and QA fix passes. Aider and OpenHands remain placeholders.
- Codex CLI uses the worker machine's local `codex login` auth or environment, not decrypted dashboard API keys.
- A successful local factory run requires internet access for Codex/Flutter dependencies, local Codex auth, Flutter, Java, Android SDK/platform tools, Postgres, Redis, and the worker daemon.
- MinIO is included, but artifacts are stored as local workspace paths in MVP.
- The Docker worker image is optional and best for connectivity checks; use the local worker for real Flutter, Android, and Codex CLI runs.
- iOS build is a macOS placeholder; Windows is Android-only.
- No production publishing or store account automation is implemented.
- Dashboard/API auth is not implemented yet; run on trusted local networks only.

## Next steps

- Add Aider/OpenHands provider implementations behind the same worker adapter boundary.
- Add dashboard auth.
- Upload artifacts to MinIO and expose signed download links.
- Add legal trend/review connectors with cache and rate limits.
- Add human approval workflow for release candidates.
