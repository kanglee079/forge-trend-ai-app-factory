from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://factory:factory@localhost:5432/factory"
    redis_url: str = "redis://localhost:6379/0"
    pipeline_queue_name: str = "project_pipeline"
    worker_stale_seconds: int = 60
    factory_secret_key: str = Field(default="")
    local_artifact_root: str = "workspaces"
    runtime_state_path: str = ".runtime/factory_state.json"

    @field_validator("factory_secret_key")
    @classmethod
    def ensure_secret_key(cls, value: str) -> str:
        if value and value != "replace-with-fernet-key":
            return value
        return Fernet.generate_key().decode()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
