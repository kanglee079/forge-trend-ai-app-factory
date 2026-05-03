import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas import AppSettings, AppSettingsPatch, FactoryState, FactoryStatePatch


def runtime_state_path() -> Path:
    path = Path(settings.runtime_state_path)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def default_state() -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "settings": {
            "default_provider": "openai",
            "default_model": "gpt-5.2",
            "max_fix_iterations": 3,
            "workspace_root": "workspaces",
            "auto_refresh_seconds": 5,
            "notifications_enabled": True,
            "theme": "system",
            "daily_budget_usd": "5",
            "monthly_budget_usd": "100",
            "feature_flags": {
                "trend_radar": False,
                "provider_key_network_test": False,
                "minio_artifacts": False,
                "release_approval": False,
            },
            "updated_at": timestamp,
        },
        "factory": {"mode": "running", "updated_at": timestamp},
    }


def read_state() -> dict[str, Any]:
    path = runtime_state_path()
    if not path.exists():
        state = default_state()
        write_state(state)
        return state
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        loaded = {}
    state = default_state()
    state["settings"].update(loaded.get("settings", {}))
    state["factory"].update(loaded.get("factory", {}))
    return state


def write_state(state: dict[str, Any]) -> None:
    path = runtime_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")


def get_app_settings() -> AppSettings:
    return AppSettings(**read_state()["settings"])


def patch_app_settings(payload: AppSettingsPatch) -> AppSettings:
    state = read_state()
    patch = payload.model_dump(exclude_unset=True)
    if "feature_flags" in patch:
        feature_flags = dict(state["settings"].get("feature_flags", {}))
        feature_flags.update(patch.pop("feature_flags") or {})
        state["settings"]["feature_flags"] = feature_flags
    state["settings"].update({key: value for key, value in patch.items() if value is not None})
    state["settings"]["updated_at"] = now_iso()
    write_state(state)
    return AppSettings(**state["settings"])


def get_factory_state() -> FactoryState:
    return FactoryState(**read_state()["factory"])


def patch_factory_state(payload: FactoryStatePatch) -> FactoryState:
    mode = payload.mode.strip().lower()
    if mode not in {"running", "paused", "stopped"}:
        raise ValueError("Factory mode must be running, paused, or stopped")
    state = read_state()
    state["factory"] = {"mode": mode, "updated_at": now_iso()}
    write_state(state)
    return FactoryState(**state["factory"])
