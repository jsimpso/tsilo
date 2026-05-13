"""Application configuration loaded from environment variables (12-factor)."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    app_base_url: str = Field(default="http://localhost:8000", alias="APP_BASE_URL")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://tsilo:tsilo@localhost:5432/tsilo",
        alias="DATABASE_URL",
    )

    # S3 Storage
    s3_bucket: str = Field(default="tsilo-modules", alias="S3_BUCKET")
    s3_access_key_id: str = Field(default="minioadmin", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="minioadmin", alias="S3_SECRET_ACCESS_KEY")
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    # OIDC Authentication
    oidc_issuer: str = Field(default="https://your-oidc-provider.com", alias="OIDC_ISSUER")
    oidc_client_id: str = Field(default="tsilo-dev", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(default="http://localhost:8000/auth/callback", alias="OIDC_REDIRECT_URI")

    # Security
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    csrf_secret_key: str = Field(default="change-me-in-production", alias="CSRF_SECRET_KEY")
    admin_group: str = Field(default="tsilo-admins", alias="ADMIN_GROUP")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def sync_database_url(self) -> str:
        """Return synchronous database URL for Alembic migrations."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
