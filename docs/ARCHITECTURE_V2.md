# ForgeTrend Architecture V2

ForgeTrend V2 is organized as five layers:

1. Simple Mode UX: Vietnamese-first flows for creating an app without exposing worker, queue, port, Codex, or E2E concepts.
2. Product Studio: ideas, briefs, PRD, app blueprint, generated candidates, store assets, reports, and roadmap decisions.
3. Agent Runtime: research, product, UX, code, QA, policy, quality, store, and growth agents.
4. Evaluation & Quality System: product score, journey gate, ASO/store gate, localization gate, policy safety, and technical QA.
5. Scale Layer: worker pool, provider/model routing, budgets, retries, artifact registry, run history, replay, and rollback.

The dashboard is the local control plane. The FastAPI service owns durable state and queue entry points. The worker daemon owns execution and artifact generation. Generated Flutter apps remain local workspaces and are never automatically published.

## Runtime Separation

- Control Plane: FastAPI, dashboard, settings, project history, artifacts, workers.
- Agent Runtime: daemon, provider adapters, app archetypes, QA/policy/quality gates.
- Desktop Shell: optional Electron wrapper for local-first launch and environment status.

## Production Principles

- Flows are deterministic orchestration; agents are creative workers inside bounded steps.
- Every generated candidate needs human approval before release.
- Every code pass should have artifacts, logs, and quality reports.
- Weak apps should become `NEEDS_HUMAN_REVIEW`, not release candidates.
