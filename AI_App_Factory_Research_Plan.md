# AI App Factory — Research & Implementation Plan

**Mục tiêu:** xây một hệ thống “Trend-to-App Factory” chạy được trên **Windows và macOS**, có giao diện trực quan, cho phép nhập API key vào dashboard, tự nghiên cứu trend, tạo ý tưởng khác biệt, sinh PRD/UI/code, build/test/fix lặp lại, rồi xuất bản nội bộ/beta khi đạt tiêu chí chất lượng.

> Nguyên tắc bắt buộc: hệ thống **không clone/copy y nguyên app khác**. Nó chỉ lấy tín hiệu thị trường, phân tích điểm yếu, tạo sản phẩm mới có USP riêng, UI riêng, tên riêng, nội dung riêng và policy gate riêng để tránh spam/copycat.

---

## 1. Kết luận nghiên cứu GitHub

Sau khi rà các repo liên quan đến autonomous coding agent, app builder, workflow agent, app-store research và release automation, các dự án đáng học hỏi nhất là:

| Nhóm | Repo/dự án | Mức nên học | Lý do chọn |
|---|---|---:|---|
| Coding agent core | `OpenHands/OpenHands` | Rất cao | Có SDK, CLI, Local GUI, REST API, agent có thể sửa code/chạy lệnh; repo lớn, có nhiều release, phù hợp làm mẫu “coding worker”. |
| Local app builder UI | `dyad-sh/dyad` | Rất cao | Local AI app builder, BYOK, chạy Mac/Windows, mô hình UX đúng với yêu cầu “ném key vào là chạy”. |
| Managed agent platform | `multica-ai/multica` | Rất cao | Có dashboard quản lý agent, daemon local, hỗ trợ Codex/Claude/OpenClaw/Gemini, kiến trúc Next.js + Go + PostgreSQL + pgvector. |
| Parallel coding workspace | `generalaction/emdash` | Cao | Desktop ADE, chạy nhiều coding agents song song, mỗi agent trong git worktree riêng, hỗ trợ macOS/Windows/Linux và SSH remote. |
| Continuous workflow agent | `Significant-Gravitas/AutoGPT` | Cao | Có Agent Builder, Workflow Management, Monitoring; có installer một dòng cho macOS/Linux và Windows PowerShell. |
| Bug-fix loop | `SWE-agent/SWE-agent` | Cao | Dùng GitHub issue làm input rồi tự sửa lỗi; phù hợp học vòng `issue → patch → test → retry`. |
| Repo-aware coding | `Aider-AI/aider` | Cao | Map codebase, tự commit, lint/test hook; phù hợp làm fallback code editor/patch agent. |
| Agent orchestration | `crewAIInc/crewAI` | Trung bình-cao | Framework role-based multi-agent; phù hợp cho Research/PRD/Policy/QA agents. |
| ASO/trend research | `facundoolano/aso` | Trung bình | Có keyword difficulty/traffic, suggestion; nhưng dựa vào scraper nên phải có rate limit và fallback API trả phí. |
| Release automation | `fastlane/fastlane` | Cao | Upload Android/iOS metadata, screenshots, binaries; dùng cho internal testing/TestFlight/Play tracks. |
| Codex CLI | `openai/codex` | Cao | Coding agent terminal; nên tích hợp làm một provider trong worker. Windows nên chạy qua WSL2 nếu cần độ ổn định. |

### Repo không nên lấy làm core ngay

Một số repo tên nghe rất giống “autonomous app builder agent” nhưng nhỏ, ít sao, ít docs, không đủ bằng chứng vận hành thật. Chỉ nên tham khảo ý tưởng, không làm nền móng.

---

## 2. Bài học rút ra từ các dự án hoạt động được

### 2.1. Dashboard + daemon là kiến trúc đúng

Multica và Emdash đều tách rõ:

```text
Control UI
  ↓
Backend/orchestrator
  ↓
Local daemon/worker
  ↓
Coding CLI / shell / git worktree
```

Dự án của chúng ta cũng nên đi theo hướng này, vì bạn muốn cài trên nhiều máy trống, mỗi máy có API key/agent riêng.

### 2.2. Không để agent code trực tiếp trong workspace chính

Nên dùng:

```text
1 ý tưởng = 1 project
1 task = 1 branch
1 agent run = 1 git worktree
1 vòng fix = 1 commit
```

Lý do: dễ rollback, dễ so sánh kết quả, tránh agent phá repo.

### 2.3. Phải có vòng test/fix tự động nhưng có giới hạn

Không dùng vòng lặp vô hạn. Dùng loop có tiêu chí dừng:

```text
while not DefinitionOfDone and iteration < max_iterations:
    run_build()
    run_tests()
    analyze_errors()
    patch_code()
    commit()
    policy_check()
    cost_check()
```

Nếu quá số vòng mà vẫn fail thì chuyển trạng thái `NEEDS_HUMAN_REVIEW`.

### 2.4. Research trend không nên phụ thuộc scraper lậu

Scraper app store dễ gãy, bị throttle, hoặc vi phạm điều khoản. Hệ thống nên ưu tiên:

1. API hợp lệ: Appfigures, Sensor Tower/AppTweak/AppMagic nếu có ngân sách.
2. Open-source ASO/scraper chỉ dùng mức nhẹ, có cache/rate limit.
3. Reddit/Product Hunt/TikTok/YouTube comments chỉ dùng để lấy tín hiệu nhu cầu, không copy nội dung.

---

## 3. Kiến trúc hệ thống đề xuất

Tên dự án: **ForgeTrend AI App Factory**

```text
┌──────────────────────────────────────────────┐
│ Dashboard Web UI                              │
│ API Keys · Workers · Ideas · Runs · QA · ASO  │
└───────────────────────┬──────────────────────┘
                        │
┌───────────────────────▼──────────────────────┐
│ Orchestrator API                              │
│ Auth · DB · Queue · Workflow · Cost · Secrets │
└───────────┬─────────────────────┬────────────┘
            │                     │
┌───────────▼──────────┐  ┌───────▼────────────┐
│ Postgres + pgvector  │  │ Redis / Queue       │
│ ideas/runs/memory    │  │ jobs/events         │
└──────────────────────┘  └────────────────────┘
            │
┌───────────▼──────────────────────────────────┐
│ Worker Daemon per Machine                     │
│ Trend · PRD · UX · Code · QA · Build · Policy │
└───────────┬──────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────┐
│ Sandboxed Project Workspaces                  │
│ Flutter app · backend · tests · store assets  │
└──────────────────────────────────────────────┘
```

---

## 4. Tech stack chuẩn cho Windows/macOS

### 4.1. Core stack

| Layer | Công nghệ |
|---|---|
| Dashboard | Next.js + React + Tailwind + shadcn/ui |
| API backend | FastAPI hoặc NestJS |
| Workflow queue | Redis + BullMQ nếu dùng Node, hoặc Celery/RQ nếu dùng Python |
| Database | PostgreSQL + pgvector |
| File storage | MinIO hoặc local volume |
| Worker daemon | Python hoặc Node.js |
| Coding providers | Codex CLI, Aider, OpenHands local, optional Claude/Gemini/OpenClaw |
| Mobile app output | Flutter |
| Android build | Flutter SDK + Android SDK |
| iOS build | macOS only, Xcode + Flutter |
| Release automation | Fastlane |
| Container | Docker Compose |

### 4.2. Cross-platform rule

| Máy | Chạy được gì |
|---|---|
| Windows 10/11 | Dashboard, orchestrator, Android build, worker daemon, Flutter Android, Codex qua WSL2 khuyến nghị |
| macOS Apple Silicon/Intel | Dashboard, orchestrator, Android build, iOS build, TestFlight/App Store upload |
| Linux/VPS | Dashboard, orchestrator, backend worker, trend/research jobs; không build iOS |

> iOS build bắt buộc cần macOS + Xcode. Windows chỉ nên build Android hoặc điều phối worker từ xa.

---

## 5. Modules phải có

### 5.1. API Key Manager

Yêu cầu:

- Nhập nhiều API key.
- Mỗi key có provider, label, daily budget, monthly budget.
- Không lưu plaintext.
- Không in key ra log.
- Gán key cho worker/job.
- Tự disable key nếu vượt ngân sách.

Bảng DB:

```sql
CREATE TABLE api_keys (
  id UUID PRIMARY KEY,
  provider TEXT NOT NULL,
  label TEXT,
  encrypted_key TEXT NOT NULL,
  status TEXT DEFAULT 'active',
  daily_budget_usd NUMERIC DEFAULT 5,
  monthly_budget_usd NUMERIC DEFAULT 100,
  total_estimated_spend_usd NUMERIC DEFAULT 0,
  assigned_worker_id UUID,
  created_at TIMESTAMPTZ DEFAULT now(),
  last_used_at TIMESTAMPTZ
);
```

### 5.2. Worker Manager

Theo dõi từng máy:

```text
machine_id
hostname
os: windows/macos/linux
cpu/ram
has_flutter
has_android_sdk
has_xcode
has_docker
has_codex
has_aider
status
current_job
last_heartbeat
```

### 5.3. Trend Research Engine

Nguồn dữ liệu ưu tiên:

1. Appfigures hoặc app intelligence API hợp lệ.
2. Google Play/App Store metadata từ nguồn hợp lệ.
3. facundoolano/aso cho keyword score nếu cần.
4. Reddit/Product Hunt/Hacker News/TikTok trend nếu có connector/API.
5. Review mining từ app công khai, có cache/rate limit.

Output:

```json
{
  "trend": "AI visa photo for students",
  "category": "Travel / Utility",
  "evidence": [
    "top chart rank movement",
    "review complaints",
    "keyword demand",
    "competitor weakness"
  ],
  "opportunity_score": 84,
  "policy_risk": "low",
  "recommended_mvp": ["photo crop", "background replace", "country preset", "checklist"]
}
```

### 5.4. Opportunity & Originality Engine

Không cho phép:

- Dùng tên/icon/brand của app khác.
- UI layout quá giống.
- Tạo nhiều app chỉ đổi màu/đổi text.
- Webview wrapper không có giá trị riêng.
- App quá ít chức năng.

Điểm chấm:

```text
Opportunity Score =
Demand Score
+ Pain Score
+ Monetization Score
+ Build Feasibility
+ Differentiation
- Policy Risk
- IP/Trademark Risk
- Clone Similarity Risk
```

### 5.5. PRD Agent

Tạo:

```text
Product brief
Target user
Problem
Core USP
Competitor gap
MVP scope
Screen list
Data model
Monetization
Risk checklist
Definition of Done
```

### 5.6. UX/UI Agent

Tạo:

```text
Design system
Color palette
Typography
Screen wireframe
Loading/error/empty states
Onboarding
Paywall
Permission flows
Screenshot plan
```

### 5.7. Code Agent

Provider gợi ý:

1. Codex CLI: task coding chính.
2. Aider: patch nhanh, repo-aware, auto commit.
3. OpenHands: local GUI/API hoặc agent runner.
4. Optional Emdash-style worktree manager.

Code agent phải chạy trong sandbox:

```text
/workspaces/{project_id}/repo
/workspaces/{project_id}/worktrees/{run_id}
```

### 5.8. QA Agent

Tự chạy:

```bash
flutter pub get
flutter analyze
dart format --set-exit-if-changed .
flutter test
flutter build apk --debug
flutter build appbundle --release
```

Nếu macOS có Xcode:

```bash
flutter build ios --release
flutter build ipa
```

### 5.9. Policy Agent

Check:

```text
Google Play repetitive content / minimum functionality
Apple copycat / incomplete app / spam
Permissions
Privacy policy
AI data disclosure
Trademark/name/icon similarity
Store metadata keyword stuffing
```

### 5.10. Release Agent

Android:

```text
build AAB
generate metadata
generate screenshots
fastlane supply internal/closed track
```

iOS:

```text
build IPA
upload TestFlight
generate metadata/screenshots
fastlane deliver
```

Production release nên có nút `Approve Release`.

---

## 6. Project structure đề xuất

```text
forge-trend-ai-app-factory/
  README.md
  docker-compose.yml
  .env.example

  apps/
    dashboard/                 # Next.js UI
    worker-desktop/            # optional Tauri/Electron later

  services/
    api/                       # FastAPI/NestJS orchestrator
    scheduler/                 # cron/scheduled jobs
    policy-engine/
    trend-engine/

  workers/
    daemon/                    # local worker daemon
    agents/
      trend_agent/
      review_mining_agent/
      opportunity_agent/
      prd_agent/
      ux_agent/
      code_agent/
      qa_agent/
      policy_agent/
      release_agent/

  packages/
    shared/
    sdk/

  templates/
    flutter_mobile_app/
    firebase_backend/
    node_backend/

  prompts/
    system/
    agents/
    bootstrap_project_prompt.md

  scripts/
    bootstrap_mac.sh
    bootstrap_windows.ps1
    doctor.py
    start_dev.sh
    start_dev.ps1
    install_flutter_mac.sh
    install_flutter_windows.ps1

  workspaces/
    .gitkeep

  docs/
    RESEARCH_GITHUB.md
    ARCHITECTURE.md
    SECURITY.md
    POLICY_GATES.md
    ROADMAP.md
```

---

## 7. Bootstrap: cài lên máy trống

### 7.1. macOS bootstrap

File: `scripts/bootstrap_mac.sh`

Nhiệm vụ:

```bash
#!/usr/bin/env bash
set -e

# 1. Homebrew
if ! command -v brew >/dev/null 2>&1; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# 2. Core tools
brew install git node pnpm python@3.12 go redis postgresql@16 watchman jq
brew install --cask docker visual-studio-code

# 3. Flutter
if ! command -v flutter >/dev/null 2>&1; then
  brew install --cask flutter
fi

# 4. Codex / Aider
npm install -g @openai/codex
python3 -m pip install --user aider-install
python3 -m aider_install

# 5. Fastlane
brew install ruby
gem install fastlane

# 6. Project setup
pnpm install
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
```

### 7.2. Windows bootstrap

File: `scripts/bootstrap_windows.ps1`

Nhiệm vụ:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# 1. Install core tools
winget install --id Git.Git -e --silent
winget install --id Docker.DockerDesktop -e --silent
winget install --id OpenJS.NodeJS.LTS -e --silent
winget install --id Python.Python.3.12 -e --silent
winget install --id Microsoft.VisualStudioCode -e --silent

# 2. Enable WSL2 for better Codex/Linux tooling
wsl --install -d Ubuntu

# 3. Package managers
npm install -g pnpm
npm install -g @openai/codex

# 4. Aider
python -m pip install --user aider-install
python -m aider_install

# 5. Flutter SDK
winget install --id Google.Flutter -e --silent

# 6. Start project
pnpm install
docker compose up -d postgres redis minio
pnpm db:migrate
pnpm dev
```

> Ghi chú: Windows cần Docker Desktop chạy xong trước khi `docker compose up`. Nếu dùng Codex full-auto ổn định hơn, nên chạy worker trong WSL2.

---

## 8. Docker Compose MVP

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: factory
      POSTGRES_PASSWORD: factory
      POSTGRES_DB: factory
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: factory
      MINIO_ROOT_PASSWORD: factory123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data

  api:
    build: ./services/api
    env_file: .env
    depends_on:
      - postgres
      - redis
      - minio
    ports:
      - "8080:8080"

  dashboard:
    build: ./apps/dashboard
    env_file: .env
    depends_on:
      - api
    ports:
      - "3000:3000"

  worker-daemon:
    build: ./workers/daemon
    env_file: .env
    depends_on:
      - api
      - redis
    volumes:
      - ./workspaces:/workspaces
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  pgdata:
  miniodata:
```

---

## 9. Definition of Done cho mỗi app

Một app chỉ được chuyển sang `RELEASE_CANDIDATE` khi đạt:

```text
PRD complete: pass
Originality score >= 75/100
Policy risk: low or medium-low
Flutter analyze: 0 errors
Unit tests: pass
Critical integration flow: pass
Android debug build: pass
Android release AAB: pass
No hardcoded API keys/secrets
No trademark/copycat naming
No unnecessary permissions
Privacy policy draft generated
Store metadata generated
Screenshots generated
Human review required before production
```

---

## 10. Roadmap triển khai

### Phase 0 — Research freeze, 1-2 ngày

- Chốt repo học hỏi.
- Chốt stack.
- Chốt policy rule.
- Chốt database schema.

### Phase 1 — Skeleton chạy được, 3-5 ngày

Deliverables:

```text
dashboard login local
API key input encrypted
worker heartbeat
job queue
project workspace creation
logs viewer
```

### Phase 2 — Generate app MVP, 5-7 ngày

Deliverables:

```text
Idea manually nhập vào
PRD Agent tạo spec
Code Agent tạo Flutter template
QA Agent chạy analyze/test/build
Fix loop tối đa 10 vòng
```

### Phase 3 — Trend/review engine, 7-10 ngày

Deliverables:

```text
keyword collector
competitor app collector
review mining
opportunity scoring
originality scoring
```

### Phase 4 — Multi-machine, 5-7 ngày

Deliverables:

```text
register worker by machine token
assign job to worker
each worker uses assigned API key
parallel worktrees
machine capability detection
```

### Phase 5 — Release pipeline, 7-14 ngày

Deliverables:

```text
Android internal testing upload
iOS TestFlight upload on macOS worker
ASO metadata generator
screenshot generator
policy checklist
manual approval gate
```

---

## 11. Prompt chuẩn để khởi tạo dự án

Xem file `AI_App_Factory_Bootstrap_Prompt.md` đi kèm. Prompt đó được thiết kế để ném vào Codex/OpenHands/Aider/Cursor/Antigravity để khởi tạo repo theo đúng kiến trúc trên.

---

## 12. Nguồn nghiên cứu chính

- OpenHands: https://github.com/OpenHands/OpenHands
- Dyad: https://github.com/dyad-sh/dyad
- Multica: https://github.com/multica-ai/multica
- Emdash: https://github.com/generalaction/emdash
- AutoGPT: https://github.com/Significant-Gravitas/AutoGPT
- SWE-agent: https://github.com/SWE-agent/SWE-agent
- Aider: https://github.com/Aider-AI/aider
- CrewAI: https://github.com/crewAIInc/crewAI
- ASO library: https://github.com/facundoolano/aso
- Fastlane Play upload: https://docs.fastlane.tools/actions/upload_to_play_store/
- Fastlane App Store upload: https://docs.fastlane.tools/actions/appstore/
- OpenAI Codex CLI: https://help.openai.com/en/articles/11096431-openai-codex-cli-getting-started
- OpenAI API key safety: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety
- Google Play spam/repetitive content: https://support.google.com/googleplay/android-developer/answer/9899034
- Google Play functionality/user experience: https://support.google.com/googleplay/android-developer/answer/16329168
- Apple App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
