# Cài ForgeTrend một chạm trên Windows

Mục tiêu: giải nén folder, bấm `run.bat`, ForgeTrend tự kiểm tra dependency, cài phần an toàn khi có thể, khởi động database, migration, worker, dashboard và desktop.

## Cách chạy

1. Mở folder ForgeTrend.
2. Bấm đúp `run.bat`.
3. Nếu Windows hỏi quyền admin khi cài dependency bằng `winget`, hãy đọc kỹ hộp thoại rồi xác nhận nếu bạn đồng ý.
4. Nếu Docker Desktop vừa được cài, mở Docker Desktop, đợi trạng thái Ready, rồi chạy lại `run.bat`.

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

## Khi thiếu dependency

Terminal sẽ hiện:

- Lỗi ở bước nào
- Nguyên nhân
- Lệnh có thể copy
- File log trong `logs/bootstrap-windows.log`

ForgeTrend không tự động publish app lên Google Play/App Store.
