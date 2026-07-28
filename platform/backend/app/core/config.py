from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://aster:aster@localhost:5432/aster"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "aster-artifacts"
    openalex_api_key: str | None = None
    crossref_mailto: str | None = None
    literature_timeout_seconds: int = 15
    dmlf_adapter_enabled: bool = False
    dmlf_bridge_endpoint: str | None = None
    dmlf_requested_nodes: int = 1
    dmlf_poll_seconds: int = 2
    dmlf_timeout_seconds: int = 1800
    jwt_secret: str = "development-only-secret-change-me"
    jwt_expires_minutes: int = 1440


@lru_cache
def get_settings() -> Settings:
    return Settings()
