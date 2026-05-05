#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs"
LOG_PATH="$LOG_DIR/bootstrap.log"
mkdir -p "$LOG_DIR"
cd "$ROOT"

step() {
  echo "[$1/12] $2"
  printf '[%s] [%s/12] %s\n' "$(date -Iseconds)" "$1" "$2" >> "$LOG_PATH"
}

fix() {
  echo ""
  echo "Cần xử lý: $1"
  echo "Lý do: $2"
  echo "Lệnh/hướng dẫn gợi ý:"
  echo "  $3"
  echo "Log: $LOG_PATH"
  printf 'FIX %s :: %s :: %s\n' "$1" "$2" "$3" >> "$LOG_PATH"
}

has() {
  command -v "$1" >/dev/null 2>&1
}

echo "ForgeTrend V3 bootstrap macOS"
echo "Mục tiêu: kiểm tra dependency, cài phần an toàn khi có thể, rồi mở ForgeTrend."
echo "ForgeTrend không tự động publish app lên store."
printf '========== ForgeTrend bootstrap macOS %s ==========\n' "$(date -Iseconds)" >> "$LOG_PATH"

step 1 "Kiểm tra Node.js"
if ! has node; then
  if has brew; then
    brew install node
  else
    fix "Node.js" "Máy chưa có Homebrew nên không tự cài Node." '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" && brew install node'
    exit 1
  fi
fi

step 2 "Kiểm tra pnpm/corepack"
if ! has pnpm; then
  if has corepack; then
    corepack enable
    corepack prepare pnpm@latest --activate
  else
    npm install -g pnpm
  fi
fi

step 3 "Kiểm tra Git và internet"
if ! has git; then
  if has brew; then brew install git; else fix "Git" "Chưa có Git/Homebrew." "xcode-select --install"; exit 1; fi
fi
if ! curl -I --max-time 8 https://github.com >/dev/null 2>&1; then
  fix "Internet" "Không truy cập được GitHub/pub.dev; pnpm và Flutter có thể fail." "Kiểm tra VPN/firewall mạng rồi chạy lại run.command"
fi

step 4 "Kiểm tra Python"
if ! has python3; then
  if has brew; then brew install python; else fix "Python" "Chưa có Python/Homebrew." "brew install python"; exit 1; fi
fi

step 5 "Kiểm tra Docker Desktop"
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

step 6 "Kiểm tra Flutter và Android SDK"
if ! has flutter; then
  fix "Flutter" "Cần Flutter để build APK; dashboard vẫn có thể mở nhưng factory run sẽ fail QA." "brew install --cask flutter"
fi
if ! has adb && [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
  fix "Android SDK" "Cần Android SDK/adb để build và test APK." "Cài Android Studio, mở SDK Manager, cài Android SDK Platform Tools, rồi set ANDROID_HOME"
fi

step 7 "Kiểm tra Java và Codex CLI"
if ! has java; then
  fix "Java" "JDK cần cho Android build." "brew install --cask temurin@17"
fi
if ! has codex; then
  echo "Codex CLI chưa có. ForgeTrend vẫn chạy deterministic mode; có thể cài sau bằng npm install -g @openai/codex."
fi

step 8 "Kiểm tra port đang dùng"
if ! node scripts/doctor_ports.mjs; then
  fix "Port" "Có thể có service cũ đang chiếm 3000/8000/5432/6379/9000." "Đọc logs/bootstrap.log và kill PID stale nếu doctor báo WARN"
fi

step 9 "Cài package Node"
pnpm install --frozen-lockfile=false

step 10 "Thiết lập Python và secret cục bộ"
pnpm setup:python
.venv/bin/python scripts/ensure_env_secret.py

step 11 "Khởi động database và chạy migration"
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm db:schema-check

step 12 "Mở ForgeTrend"
node scripts/bootstrap_common.mjs launch
