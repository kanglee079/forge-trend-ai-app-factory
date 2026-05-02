import os
import re
import subprocess
from pathlib import Path


DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/(?:\s|$)"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bdiskutil\b"),
    re.compile(r"\bmkfs\b"),
]


def ensure_inside_workspace(workspace: Path, cwd: Path) -> None:
    workspace_real = workspace.resolve()
    cwd_real = cwd.resolve()
    if not str(cwd_real).startswith(str(workspace_real)):
        raise RuntimeError(f"Refusing to run outside workspace: {cwd_real}")


def run_safe(
    command: list[str],
    cwd: Path,
    workspace: Path,
    timeout: int = 600,
    stdin: str | None = None,
    preserve_codex_auth: bool = False,
) -> subprocess.CompletedProcess[str]:
    ensure_inside_workspace(workspace, cwd)
    printable = " ".join(command)
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(printable):
            raise RuntimeError(f"Blocked dangerous command: {printable}")
    env = os.environ.copy()
    if not preserve_codex_auth:
        env.pop("OPENAI_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)
    else:
        env.pop("ANTHROPIC_API_KEY", None)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
