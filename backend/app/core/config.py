"""환경 변수 기반 설정 (pydantic-settings)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FORBIDDEN_JWT_SECRETS = frozenset(
    {
        "dev-secret-change-in-production",
        "change-me-to-a-long-random-secret-in-production",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production"] = Field(
        default="development",
        validation_alias="ENVIRONMENT",
    )

    database_url: str = "postgresql+asyncpg://messenger:messenger@localhost:5432/messenger"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 100 * 1024 * 1024
    chunk_size_bytes: int = 1024 * 1024
    cors_origins: str = "http://localhost,http://127.0.0.1"

    # 로깅·보안
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    trusted_hosts: str = Field(
        default="",
        description="쉼표 구분 호스트. 비우면 TrustedHost 미들웨어 비활성.",
        validation_alias="TRUSTED_HOSTS",
    )
    ws_auth_timeout_seconds: float = Field(default=15.0, validation_alias="WS_AUTH_TIMEOUT_SECONDS")
    metrics_enabled: bool = Field(default=True, validation_alias="METRICS_ENABLED")

    @field_validator("database_url")
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("jwt_secret")
    @classmethod
    def jwt_non_empty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("JWT_SECRET은 비워 둘 수 없습니다.")
        return s

    @model_validator(mode="after")
    def production_secrets_and_logging(self) -> Settings:
        if self.environment == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError(
                    "ENVIRONMENT=production 일 때 JWT_SECRET은 최소 32자 이상의 무작위 문자열이어야 합니다."
                )
            if self.jwt_secret in FORBIDDEN_JWT_SECRETS:
                raise ValueError("production에서 예시/기본 JWT_SECRET 값은 사용할 수 없습니다.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        hosts = [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]
        return hosts


settings = Settings()
