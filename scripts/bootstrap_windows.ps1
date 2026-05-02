$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

winget install --id Git.Git -e --silent
winget install --id Docker.DockerDesktop -e --silent
winget install --id OpenJS.NodeJS.LTS -e --silent
winget install --id Python.Python.3.12 -e --silent
winget install --id Microsoft.VisualStudioCode -e --silent
winget install --id Google.Flutter -e --silent

Write-Host "Enabling WSL2 guidance. If Windows requests a reboot, restart and rerun this script."
wsl --install -d Ubuntu

npm install -g pnpm
npm install -g @openai/codex
python -m pip install --user aider-install
python -m aider_install

pnpm install
pnpm setup:python
.\.venv\Scripts\python.exe scripts\ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
