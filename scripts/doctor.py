#!/usr/bin/env python3
import shutil
import subprocess
import sys


def python_command() -> list[str]:
    for command in (["python3", "--version"], ["python", "--version"], ["py", "--version"]):
        if shutil.which(command[0]):
            return command
    return ["python3", "--version"]


CHECKS = [
    ("git", ["git", "--version"]),
    ("node", ["node", "--version"]),
    ("pnpm", ["pnpm", "--version"]),
    ("python", python_command()),
    ("docker", ["docker", "--version"]),
    ("docker compose", ["docker", "compose", "version"]),
    ("flutter", ["flutter", "--version"]),
    ("codex", ["codex", "--version"]),
    ("aider", ["aider", "--version"]),
]


def run(command: list[str]) -> tuple[bool, str]:
    if not shutil.which(command[0]):
        return False, "not found"
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except Exception as exc:
        return False, str(exc)
    output = (result.stdout or result.stderr).strip().splitlines()
    return result.returncode == 0, output[0] if output else f"exit {result.returncode}"


def main() -> int:
    failed = 0
    print("ForgeTrend doctor")
    print("=================")
    for label, command in CHECKS:
        ok, detail = run(command)
        status = "OK" if ok else "WARN"
        if not ok and label in {"git", "node", "pnpm", "python", "docker", "docker compose"}:
            failed += 1
        print(f"{status:4} {label:14} {detail}")
    if failed:
        print("\nRequired checks failed. Install missing tools before running the full stack.")
        return 1
    print("\nCore checks passed. Flutter/Codex/Aider warnings only block the worker features that need them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
