#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

brew install git node pnpm python go jq || true

if ! command -v docker >/dev/null 2>&1; then
  brew install --cask docker
  echo "Open Docker Desktop, finish onboarding, then rerun this script if docker is not ready."
fi

if ! command -v flutter >/dev/null 2>&1; then
  brew install --cask flutter
fi

npm install -g @openai/codex
python3 -m pip install --user aider-install || true
python3 -m aider_install || true
brew install fastlane || gem install fastlane

pnpm install
pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
