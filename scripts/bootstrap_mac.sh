#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_PATH="$LOG_DIR/bootstrap-macos.log"
mkdir -p "$LOG_DIR"
cd "$ROOT"

step() {
  echo "[$1/9] $2"
  printf '[%s] [%s/9] %s\n' "$(date -Iseconds)" "$1" "$2" >> "$LOG_PATH"
}

fix() {
  echo ""
  echo "Không thể tự xử lý: $1"
  echo "Nguyên nhân: $2"
  echo "Lệnh gợi ý có thể copy:"
  echo "  $3"
  echo "Log: $LOG_PATH"
  printf 'FIX %s :: %s :: %s\n' "$1" "$2" "$3" >> "$LOG_PATH"
}

has() {
  command -v "$1" >/dev/null 2>&1
}

echo "ForgeTrend V3 bootstrap macOS"
echo "Mục tiêu: kiểm tra dependency, cài phần an toàn khi có thể, rồi mở ForgeTrend."
echo "Không tự động publish app lên store."

step 1 "Kiểm tra Node.js"
if ! has node; then
  if has brew; then
    brew install node
  else
    fix "Node.js" "Máy chưa có Homebrew nên không tự cài Node." '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" && brew install node'
    exit 1
  fi
fi

step 2 "Kiểm tra Git và internet"
if ! has git; then
  if has brew; then brew install git; else fix "Git" "Chưa có Git/Homebrew." "xcode-select --install"; exit 1; fi
fi
if ! curl -I --max-time 8 https://github.com >/dev/null 2>&1; then
  fix "Internet" "Không truy cập được GitHub/pub.dev; pnpm và Flutter có thể fail." "Kiểm tra VPN/firewall mạng rồi chạy lại run.command"
fi

step 3 "Kiểm tra Python"
if ! has python3; then
  if has brew; then brew install python; else fix "Python" "Chưa có Python/Homebrew." "brew install python"; exit 1; fi
fi

step 4 "Kiểm tra Docker Desktop"
if ! has docker; then
  if has brew; then
    brew install --cask docker
    fix "Docker Desktop" "Docker vừa được cài và cần mở app lần đầu." "Mở Docker Desktop, đợi Ready, rồi chạy lại run.command"
    exit 1
  else
    fix "Docker Desktop" "Full mode cần Docker Desktop." "Cài Docker Desktop từ https://www.docker.com/products/docker-desktop/"
    exit 1
  fi
fi
if ! docker info >/dev/null 2>&1; then
  fix "Docker engine" "Docker CLI có nhưng Docker Desktop chưa chạy." "Mở Docker Desktop, đợi Ready, rồi chạy lại run.command"
  exit 1
fi

step 5 "Kiểm tra Flutter, Android SDK, Java, Codex"
if ! has flutter; then
  fix "Flutter" "Không bắt buộc để mở dashboard, nhưng cần để build APK." "brew install --cask flutter"
fi
if ! has java; then
  fix "Java" "Java/JDK cần cho Android build." "brew install --cask temurin@17"
fi
if ! has codex; then
  echo "Codex CLI chưa có. ForgeTrend vẫn chạy deterministic mode; có thể cài sau bằng npm install -g @openai/codex."
fi

step 6 "Kiểm tra pnpm/corepack và cài package"
if ! has pnpm; then
  if has corepack; then
    corepack enable
    corepack prepare pnpm@latest --activate
  else
    npm install -g pnpm
  fi
fi
pnpm install --frozen-lockfile=false
pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py

step 7 "Khởi động database"
docker compose up -d postgres redis minio

step 8 "Chạy migration"
pnpm db:migrate

step 9 "Mở ForgeTrend"
node scripts/bootstrap_common.mjs launch
