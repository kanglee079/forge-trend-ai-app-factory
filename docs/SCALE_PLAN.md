# Scale Plan

ForgeTrend should scale from one local worker to many machines.

## Worker Pool

Track machine name, OS, mode, capabilities, current job, queue depth, last run, success/failure rate, assigned provider/key, daily budget, and pause/resume state.

## Provider Router

Rules:

- Deterministic for smoke/proof runs.
- Codex for coding pass when authenticated.
- Aider for refinement pass when installed.
- No LLM when budget is exceeded.
- Safe fallback to `NEEDS_HUMAN_REVIEW` when provider state is unclear.

## Durability

Persist run state, retry policy, last error, next retry time, artifacts, and evaluation history. Crash/restart should resume from the last completed checkpoint.
