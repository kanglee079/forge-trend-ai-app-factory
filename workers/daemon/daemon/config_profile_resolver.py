from __future__ import annotations

from typing import Any

from daemon.api import FactoryApi


def sanitized_runtime_config(api: FactoryApi, brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the profile for a run without exposing decrypted secrets."""
    snapshot = (brief or {}).get("runtime_config_snapshot_json") or {}
    if snapshot:
        return snapshot
    config_profile_id = (brief or {}).get("config_profile_id")
    try:
        return api.runtime_config(str(config_profile_id) if config_profile_id else None)
    except Exception:
        return {
            "config_profile_id": config_profile_id,
            "profile_name": "Fallback deterministic",
            "model_provider": "deterministic",
            "model": "deterministic",
            "review_model": "deterministic",
            "network_access": "disabled",
            "provider": {"auth_mode": "deterministic_fallback"},
            "enabled_plugins": [],
            "enabled_skills": [],
            "trusted_projects": [],
            "secrets_redacted": True,
        }


def config_summary(runtime_config: dict[str, Any]) -> dict[str, Any]:
    provider = runtime_config.get("provider") or {}
    return {
        "profile_name": runtime_config.get("profile_name"),
        "model_provider": runtime_config.get("model_provider"),
        "model": runtime_config.get("model"),
        "review_model": runtime_config.get("review_model"),
        "network_access": runtime_config.get("network_access"),
        "provider_base_url": provider.get("base_url"),
        "provider_auth_mode": provider.get("auth_mode"),
        "plugins": [item.get("plugin_id") for item in runtime_config.get("enabled_plugins", [])],
        "skills": [item.get("slug") for item in runtime_config.get("enabled_skills", [])],
        "secrets_redacted": True,
    }
