# Bootstrap Prompt — ForgeTrend AI App Factory

Bạn là Senior AI Systems Architect + Full-stack Engineer + DevOps Engineer. Hãy khởi tạo một monorepo tên `forge-trend-ai-app-factory` chạy được trên **Windows 10/11** và **macOS**, dùng Docker Compose cho core services, có dashboard trực quan để nhập API key, quản lý worker, quản lý ý tưởng app, chạy agent pipeline và xem log/test/build status.

## 0. Nguyên tắc quan trọng

Hệ thống này KHÔNG được thiết kế để clone/copy y nguyên app khác. Nó chỉ dùng market trend và review mining để tìm pain point, sau đó tạo app mới có USP riêng, UI riêng, tên riêng, nội dung riêng và policy gate để tránh copycat/spam.

Không hardcode API key. Không commit secret. Không in API key ra log. Không cho agent publish production tự động nếu chưa có human approval.

## 1. Mục tiêu MVP

Khi chạy xong repo, tôi muốn:

1. Mở dashboard tại `http://localhost:3000`.
2. Nhập nhiều API key/provider vào UI.
3. Thấy danh sách worker machine.
4. Tạo một project app mới từ idea thủ công.
5. Hệ thống tạo PRD.
6. Hệ thống tạo Flutter app skeleton.
7. Hệ thống chạy:
   - `flutter pub get`
   - `flutter analyze`
   - `flutter test`
   - `flutter build apk --debug`
8. Nếu lỗi, Code Agent đọc lỗi và sửa tối đa 10 vòng.
9. Dashboard hiển thị agent timeline, log, test status, build artifact.
10. Có policy checklist và originality checklist.
11. Có bootstrap scripts cho macOS và Windows.

## 2. Tech stack bắt buộc

- Monorepo package manager: `pnpm`
- Dashboard: Next.js + React + TypeScript + Tailwind + shadcn/ui
- Backend API: FastAPI Python hoặc NestJS TypeScript. Ưu tiên FastAPI nếu dễ triển khai nhanh.
- Database: PostgreSQL + pgvector
- Queue: Redis
- Storage: MinIO hoặc local filesystem abstraction
- Worker daemon: Python
- Mobile app output: Flutter
- Coding CLI providers:
  - Codex CLI
  - Aider
  - OpenHands adapter placeholder
- Container: Docker Compose
- OS support:
  - macOS: full support including iOS build placeholder
  - Windows: Android build + WSL2 recommendation for Codex/Unix tooling

## 3. Repo structure cần tạo

Tạo cấu trúc:

```text
forge-trend-ai-app-factory/
  README.md
  .env.example
  docker-compose.yml
  package.json
  pnpm-workspace.yaml

  apps/
    dashboard/

  services/
    api/

  workers/
    daemon/
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

  templates/
    flutter_mobile_app/

  prompts/
    agents/
      trend_agent.md
      opportunity_agent.md
      prd_agent.md
      ux_agent.md
      code_agent.md
      qa_agent.md
      policy_agent.md
      release_agent.md

  scripts/
    bootstrap_mac.sh
    bootstrap_windows.ps1
    doctor.py
    start_dev.sh
    start_dev.ps1

  docs/
    ARCHITECTURE.md
    SECURITY.md
    POLICY_GATES.md
    ROADMAP.md

  workspaces/
    .gitkeep
```

## 4. Database schema

Tạo migration SQL hoặc ORM models cho:

```text
api_keys
workers
ideas
projects
agent_runs
agent_events
builds
qa_results
policy_results
artifacts
cost_usage
```

Fields tối thiểu:

### api_keys

```text
id
provider
label
encrypted_key
status
daily_budget_usd
monthly_budget_usd
total_estimated_spend_usd
assigned_worker_id
created_at
last_used_at
```

### workers

```text
id
machine_name
os
arch
has_docker
has_flutter
has_android_sdk
has_xcode
has_codex
has_aider
status
last_heartbeat_at
current_job_id
```

### projects

```text
id
name
slug
idea_id
status
target_platforms
workspace_path
created_at
updated_at
```

### agent_runs

```text
id
project_id
agent_name
status
input_json
output_json
error_message
started_at
finished_at
iteration
```

## 5. API endpoints

Tạo endpoints:

```text
GET  /health
POST /api-keys
GET  /api-keys
PATCH /api-keys/{id}

POST /workers/register
POST /workers/{id}/heartbeat
GET  /workers

POST /ideas
GET  /ideas
POST /projects
GET  /projects
GET  /projects/{id}

POST /projects/{id}/run-pipeline
GET  /projects/{id}/events
GET  /projects/{id}/qa
GET  /projects/{id}/policy
GET  /projects/{id}/artifacts
```

## 6. Dashboard UI

Tạo pages:

```text
/
  overview cards

/api-keys
  add key modal
  provider selector
  budget fields
  masked key table

/workers
  machine status table
  capability badges

/ideas
  create idea
  opportunity score
  status board

/projects
  project table

/projects/[id]
  tabs:
    Overview
    PRD
    Agent Timeline
    Logs
    QA
    Policy
    Artifacts
    Settings
```

## 7. Worker daemon

Worker daemon cần:

1. Register với API.
2. Gửi heartbeat mỗi 15 giây.
3. Nhận job từ Redis queue.
4. Tạo workspace:
   `workspaces/{project_id}`
5. Chạy agents theo pipeline:
   - prd_agent
   - ux_agent
   - code_agent
   - qa_agent
   - policy_agent
6. Log từng step về API.
7. Commit mỗi vòng sửa bằng git.
8. Không chạy lệnh nguy hiểm ngoài workspace.

## 8. Agent behavior

### PRD Agent

Input: idea text  
Output: `prd.md` gồm:

```text
Target user
Problem
USP
Competitor gap
MVP features
Screens
Data model
Monetization
Risks
Definition of Done
```

### UX Agent

Output:

```text
design_system.md
screen_flow.md
```

### Code Agent

Tạo Flutter app từ template trong `templates/flutter_mobile_app`.

Yêu cầu Flutter project:

```text
lib/
  main.dart
  app.dart
  core/
    theme/
    widgets/
  features/
    home/
    onboarding/
    settings/
test/
```

Không cần app quá phức tạp trong MVP, nhưng phải build được.

### QA Agent

Chạy:

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

Lưu stdout/stderr vào `agent_events`.

### Fix Loop

Nếu QA fail:

1. Parse lỗi.
2. Gửi lỗi cho Code Agent.
3. Code Agent sửa.
4. Commit.
5. QA chạy lại.
6. Lặp tối đa 10 lần.

Nếu vẫn fail:

```text
project.status = NEEDS_HUMAN_REVIEW
```

### Policy Agent

Check:

```text
No copycat/trademark naming
No hardcoded keys
No excessive permissions
No minimum-functionality issue
No webview-only app
Privacy policy placeholder exists
```

Output JSON:

```json
{
  "risk": "low|medium|high",
  "passed": true,
  "issues": [],
  "required_changes": []
}
```

## 9. Bootstrap scripts

### scripts/bootstrap_mac.sh

Phải:

- cài Homebrew nếu chưa có
- cài git/node/pnpm/python/go/jq
- cài Docker Desktop hoặc nhắc mở Docker
- cài Flutter
- cài Codex CLI: `npm install -g @openai/codex`
- cài Aider
- cài Fastlane
- chạy `pnpm install`
- chạy `docker compose up -d`
- chạy migration
- chạy dev server

### scripts/bootstrap_windows.ps1

Phải:

- dùng winget để cài Git, Docker Desktop, Node LTS, Python, VS Code, Flutter
- enable WSL2 hoặc ít nhất hướng dẫn người dùng restart nếu WSL cần reboot
- cài pnpm
- cài Codex CLI
- cài Aider
- chạy `pnpm install`
- chạy `docker compose up -d`
- chạy migration
- chạy dev server

## 10. Security requirements

- API key phải encrypted at rest.
- `.env.example` không có secret thật.
- Không log key.
- Add `.gitignore` cho:
  - `.env`
  - workspaces/*
  - logs/*
  - secrets/*
  - *.p8
  - service-account*.json
- Add `docs/SECURITY.md` hướng dẫn rotate key, budget, disable key.
- Add cost limit check trước mỗi LLM call.

## 11. Không làm trong MVP

Không cần:

- Auto publish production
- Payment/IAP thật
- Crawl dữ liệu lớn
- Clone app thật
- Account Google/Apple automation đầy đủ
- iOS build thật trên Windows

Chỉ cần scaffold sạch, chạy được, có pipeline tự tạo Flutter skeleton và QA/fix loop cơ bản.

## 12. Definition of Done cho repo

Chỉ kết thúc khi:

```text
pnpm install success
docker compose up -d success
dashboard loads at localhost:3000
API health returns OK
worker registers successfully
user can add masked API key
user can create idea/project
pipeline generates PRD
pipeline creates Flutter app skeleton
QA agent can run flutter analyze/test/build
logs appear in dashboard
policy checklist appears
bootstrap_mac.sh exists
bootstrap_windows.ps1 exists
README has clear Windows/macOS setup
```

## 13. Output mong muốn

Hãy tạo code thật, không chỉ mô tả.  
Sau khi hoàn tất, in ra:

```text
How to run on macOS
How to run on Windows
Known limitations
Next steps
```
