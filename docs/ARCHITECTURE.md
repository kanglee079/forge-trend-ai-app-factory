# Architecture

ForgeTrend AI App Factory is a local-first control plane for turning original app ideas into buildable Flutter MVPs.

## Components

- Dashboard: Next.js, React, TypeScript, Tailwind, shadcn-style local components.
- API: FastAPI orchestrator with PostgreSQL, pgvector extension, Redis queue, encrypted API key metadata, and pipeline state.
- Worker daemon: Python process that registers capabilities, heartbeats, polls Redis, generates docs, controls local coding CLIs such as Codex inside project workspaces, runs QA, and posts logs back to the API.
- Storage: local workspace paths in MVP, with MinIO available in Docker Compose for future artifact storage.
- Mobile output: Flutter Android skeleton, with macOS iOS placeholder docs.

## Flow

1. User creates an idea and project in the dashboard.
2. Dashboard calls `POST /projects/{id}/run-pipeline`.
3. API marks project queued and pushes a Redis job.
4. Worker creates `workspaces/{project_id}`, runs deterministic PRD/UX scaffolding, then lets the configured local code provider customize or fix the Flutter app inside that workspace.
5. Dashboard reads events, QA results, policy results, and artifacts from the API.

## Local Coding Providers

The primary MVP provider is Codex CLI. The worker invokes `codex exec` non-interactively with the project workspace as the working root, workspace-write sandboxing, and no interactive approvals. Codex uses local machine authentication (`codex login` or supported environment configuration); the API does not decrypt stored dashboard provider keys for this path.

Aider and OpenHands are adapter placeholders.
