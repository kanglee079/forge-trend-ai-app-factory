# ForgeTrend AI App Factory

ForgeTrend is a local-first, Vietnamese-first AI app factory. You enter an idea, and the system creates PRD, design docs, Flutter source, QA report, policy report, quality report, store asset drafts, and a test APK for human review.

ForgeTrend does not auto-publish to Google Play or the App Store.

## Quick Start

Windows:

```bat
run.bat
```

macOS:

```bash
./run.command
```

Developer mode:

```bash
pnpm reset:local
pnpm dev
```

Open the dashboard and choose **Create an app from my idea**.

## Validation

```bash
pnpm db:migrate
pnpm lint
pnpm build
pnpm smoke
WORKER_ENABLE_CODEX=false pnpm e2e:factory
WORKER_ENABLE_CODEX=false pnpm e2e:factory:vi
pnpm e2e:generated-app-quality
pnpm e2e:first-run
pnpm e2e:one-click-sim
pnpm e2e:autopilot
pnpm e2e:learning
pnpm e2e:internal-test-package
pnpm e2e:ui
```

Codex mode:

```bash
WORKER_ENABLE_CODEX=true pnpm e2e:factory:codex
```

Web research mode:

```bash
RESEARCH_ENABLE_WEB=true RESEARCH_ALLOWED_URLS=https://www.producthunt.com pnpm e2e:research-web
```

## Status Meaning

- `release_candidate`: passed automated QA, policy, quality, and store-readiness gates for human review.
- `NEEDS_HUMAN_REVIEW`: blocked or requires deeper human product review.
