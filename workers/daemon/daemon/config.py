from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    worker_api_base_url: str = "http://localhost:8000"
    redis_url: str = "redis://localhost:6379/0"
    pipeline_queue_name: str = "project_pipeline"
    factory_brief_queue_name: str = "factory_brief_queue"
    worker_workspace_root: Path = Path("workspaces")
    worker_heartbeat_seconds: int = 15
    worker_max_fix_iterations: int = 10
    worker_name: str = "local-worker"
    worker_code_provider: str = "codex_cli"
    worker_codex_model: str | None = None
    worker_codex_timeout_seconds: int = 180
    worker_enable_codex: bool = True
    research_allowed_urls: str = ""
    research_allowed_domains: str = "github.com,pub.dev,producthunt.com,reddit.com"
    research_web_timeout_seconds: float = 8.0
    research_web_delay_seconds: float = 1.0


settings = WorkerSettings()
