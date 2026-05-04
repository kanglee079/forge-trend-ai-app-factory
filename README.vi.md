# ForgeTrend AI App Factory

ForgeTrend là xưởng tạo app local-first, Vietnamese-first: bạn nhập ý tưởng, hệ thống tạo PRD, thiết kế, source Flutter, QA report, policy report, quality report, store asset drafts và APK thử nghiệm để con người review.

ForgeTrend không tự động publish lên Google Play hoặc App Store.

## Ai nên dùng

- Người muốn biến ý tưởng thành app Flutter MVP để review.
- Team nhỏ muốn có pipeline tạo app, test, báo cáo và artifact rõ ràng.
- Người dùng Việt muốn trải nghiệm đơn giản trước, cấu hình nâng cao sau.

## Cách chạy đơn giản

Windows:

```bat
run.bat
```

macOS:

```bash
./run.command
```

Chế độ developer:

```bash
pnpm reset:local
pnpm dev
```

Sau đó mở dashboard và chọn **Tạo app từ ý tưởng của tôi**.

## Test quan trọng

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

Nếu Codex đã login:

```bash
WORKER_ENABLE_CODEX=true pnpm e2e:factory:codex
```

Nếu bật web research:

```bash
RESEARCH_ENABLE_WEB=true RESEARCH_ALLOWED_URLS=https://www.producthunt.com pnpm e2e:research-web
```

## Hiểu trạng thái

- `release_candidate`: app đủ điều kiện tự động để con người review tiếp.
- `NEEDS_HUMAN_REVIEW`: app có blocker hoặc cần đánh giá sâu hơn.

## Xem kết quả

Vào **Artifact Center** để mở/copy đường dẫn APK, source, PRD, quality report, store readiness report và store asset drafts.

## Tài liệu tiếng Việt

- `docs/ONE_CLICK_INSTALL_WINDOWS_VI.md`
- `docs/ONE_CLICK_INSTALL_MACOS_VI.md`
- `docs/INSTALLER_TROUBLESHOOTING_VI.md`
- `docs/SIMPLE_MODE_USER_GUIDE_VI.md`
- `docs/AUTOPILOT_ARCHITECTURE.md`
- `docs/LEARNING_MEMORY.md`
- `docs/INTERNAL_TEST_PACKAGE.md`
