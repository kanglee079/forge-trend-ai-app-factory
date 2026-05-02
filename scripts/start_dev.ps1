$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

pnpm setup:python
.\.venv\Scripts\python.exe scripts\ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
