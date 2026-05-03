import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from daemon.config import settings
from daemon.safety import run_safe


@dataclass(frozen=True)
class ProviderAdapter:
    name: str
    command: str
    enabled: bool = False

    def describe(self) -> dict[str, object]:
        return {"name": self.name, "command": self.command, "enabled": self.available}

    @property
    def available(self) -> bool:
        return shutil.which(self.command) is not None


CODEX_CLI = ProviderAdapter(name="codex_cli", command="codex")
AIDER = ProviderAdapter(name="aider", command="aider")
OPENHANDS = ProviderAdapter(name="openhands", command="openhands")

ADAPTERS = [CODEX_CLI, AIDER, OPENHANDS]


class ProviderUnavailable(RuntimeError):
    pass


def check_codex_authenticated() -> None:
    if not CODEX_CLI.available:
        raise ProviderUnavailable("Codex CLI is not installed or not on PATH")
    completed = subprocess.run([CODEX_CLI.command, "login", "status"], capture_output=True, text=True, timeout=8, check=False)
    if completed.returncode != 0:
        raise ProviderUnavailable("Codex CLI is installed but not authenticated. Run: codex login")


def run_codex_cli(prompt: str, *, cwd: Path, workspace: Path, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    if not settings.worker_enable_codex:
        raise ProviderUnavailable("Codex CLI is disabled by WORKER_ENABLE_CODEX")
    check_codex_authenticated()

    command = [
        CODEX_CLI.command,
        "exec",
        "--cd",
        str(cwd),
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--color",
        "never",
    ]
    if settings.worker_codex_model:
        command.extend(["--model", settings.worker_codex_model])
    command.append("-")

    return run_safe(
        command,
        cwd=cwd,
        workspace=workspace,
        timeout=timeout or settings.worker_codex_timeout_seconds,
        stdin=prompt,
        preserve_codex_auth=True,
    )
