# Xử lý lỗi installer ForgeTrend

## Node không có

Windows:

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

macOS:

```bash
brew install node
```

## Docker chưa sẵn sàng

Mở Docker Desktop, đợi đến khi engine Ready, rồi chạy lại `run.bat` hoặc `run.command`.

## Flutter không có

ForgeTrend vẫn mở dashboard được, nhưng chưa build APK được.

Windows:

```powershell
winget install --id Google.Flutter -e
```

macOS:

```bash
brew install --cask flutter
```

## Codex chưa login

Deterministic mode vẫn chạy được. Nếu muốn coding pass bằng Codex:

```bash
codex login
```
