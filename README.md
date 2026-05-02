# ForgeTrend AI App Factory

ForgeTrend is a local-first MVP control plane for generating original Flutter app skeletons from human-entered ideas. It is intentionally not a clone factory: the pipeline creates a PRD, UX notes, a fresh Flutter scaffold, QA/build results, and policy checks that block copycat, thin, or secret-leaking apps.

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
2. Add provider API keys in `API Keys`; they are encrypted and only masked hints are returned.
3. Log in to Codex CLI on the worker machine with `codex login` if you want the code agent to use Codex.
4. Start the worker with `pnpm dev:worker` if it is not already running.
5. Create an idea in `Ideas`.
6. Create a project in `Projects`.
7. Click `Run` or `Run pipeline`.
8. Watch project detail tabs for PRD, agent timeline, logs, QA, policy, and artifacts.

## API

Public MVP routes:

- `GET /health`
- `POST /api-keys`, `GET /api-keys`, `PATCH /api-keys/{id}`
- `POST /workers/register`, `POST /workers/{id}/heartbeat`, `GET /workers`
- `POST /ideas`, `GET /ideas`
- `POST /projects`, `GET /projects`, `GET /projects/{id}`
- `POST /projects/{id}/run-pipeline`
- `GET /projects/{id}/events`
- `GET /projects/{id}/qa`
- `GET /projects/{id}/policy`
- `GET /projects/{id}/artifacts`

The worker also uses `/internal/*` endpoints to write events and results.

## Known limitations

- Trend and review mining agents are placeholders in this MVP.
- Codex CLI is wired for code customization and QA fix passes. Aider and OpenHands remain placeholders.
- Codex CLI uses the worker machine's local `codex login` auth or environment, not decrypted dashboard API keys.
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
