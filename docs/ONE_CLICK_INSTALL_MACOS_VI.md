# Cài ForgeTrend một chạm trên macOS

Mục tiêu: bấm `run.command`, ForgeTrend tự kiểm tra dependency, hướng dẫn/cài phần an toàn, khởi động database, migration, worker, dashboard và desktop.

## Cách chạy

1. Mở folder ForgeTrend.
2. Bấm đúp `run.command`.
3. Nếu thiếu Docker Desktop, cài/mở Docker Desktop rồi chạy lại.
4. Nếu thiếu Flutter hoặc Java, bootstrap sẽ đưa lệnh gợi ý.

## Bootstrap kiểm tra

- Node.js
- Git
- Python
- Docker Desktop
- Flutter
- Android SDK/Java
- pnpm/corepack
- Codex CLI nếu muốn dùng provider thật
- Internet

Log nằm ở `logs/bootstrap-macos.log`.
