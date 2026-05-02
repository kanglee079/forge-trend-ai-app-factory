#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
