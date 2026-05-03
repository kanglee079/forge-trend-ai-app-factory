import platform
import shutil
import socket
import subprocess

from daemon.config import settings


def has_command(command: str) -> bool:
    return shutil.which(command) is not None


def command_ok(command: list[str]) -> bool:
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=8)
        return True
    except Exception:
        return False


def detect_capabilities() -> dict[str, object]:
    system = platform.system().lower()
    return {
        "machine_name": settings.worker_name if settings.worker_name != "local-worker" else socket.gethostname(),
        "os": system,
        "arch": platform.machine(),
        "has_docker": has_command("docker") and command_ok(["docker", "--version"]),
        "has_flutter": has_command("flutter") and command_ok(["flutter", "--version"]),
        "has_android_sdk": bool(shutil.which("sdkmanager") or shutil.which("adb")),
        "has_xcode": system == "darwin" and has_command("xcodebuild"),
        "has_codex": has_command("codex"),
        "has_aider": has_command("aider"),
        "worker_enable_codex": settings.worker_enable_codex,
    }
