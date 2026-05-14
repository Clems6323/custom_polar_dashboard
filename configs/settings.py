"""Application-wide configuration loaded from environment variables and .env file.

Settings are split into logical groups (Polar, Storage, App) so each layer
can depend only on the settings it needs without importing the entire config.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PolarSettings(BaseSettings):
    """Polar AccessLink API credentials and endpoint configuration."""

    client_id: str | None = Field(default=None, description="Polar AccessLink OAuth2 client ID")
    client_secret: str | None = Field(
        default=None, description="Polar AccessLink OAuth2 client secret"
    )
    redirect_uri: str = Field(
        default="http://localhost:8000/auth/polar/callback",
        description="OAuth2 redirect URI (must match the registered application)",
    )
    base_url: str = Field(
        default="https://www.polaraccesslink.com/v3",
        description="Polar AccessLink REST API base URL",
    )
    auth_url: str = Field(
        default="https://flow.polar.com/oauth2/authorization",
        description="Polar OAuth2 authorization endpoint",
    )
    token_url: str = Field(
        default="https://polarremote.com/v2/oauth2/token",
        description="Polar OAuth2 token endpoint",
    )
    request_timeout_seconds: int = Field(
        default=30, description="HTTP request timeout in seconds"
    )
    max_retry_attempts: int = Field(
        default=3, description="Maximum number of retry attempts for transient failures"
    )

    model_config = SettingsConfigDict(env_prefix="POLAR_", env_file=".env", extra="ignore")

    def require_credentials(self) -> tuple[str, str]:
        """Return (client_id, client_secret) or raise if not configured."""
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Polar credentials are not configured. "
                "Set POLAR_CLIENT_ID and POLAR_CLIENT_SECRET in your .env file."
            )
        return self.client_id, self.client_secret


class StorageSettings(BaseSettings):
    """Persistence and file-system configuration."""

    data_dir: Path = Field(default=Path("data"), description="Root data directory")
    duckdb_path: Path = Field(
        default=Path("data/polar_dashboard.duckdb"),
        description="DuckDB database file path",
    )
    parquet_dir: Path = Field(
        default=Path("data/parquet"), description="Root directory for Parquet files"
    )
    token_path: Path = Field(
        default=Path("data/tokens/polar_token.json"),
        description="Path for persisting Polar OAuth tokens",
    )

    model_config = SettingsConfigDict(env_prefix="STORAGE_", env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _ensure_directories(self) -> StorageSettings:
        """Create required directories on first load."""
        for directory in (
            self.data_dir,
            self.parquet_dir,
            self.token_path.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self


class AppSettings(BaseSettings):
    """Top-level application behaviour settings."""

    debug: bool = Field(default=False, description="Enable verbose debug logging")
    log_level: str = Field(default="INFO", description="Python logging level")
    demo_mode: bool = Field(
        default=False,
        description=(
            "Populate the dashboard with synthetic data when no real Polar "
            "sync has been performed"
        ),
    )

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")


class Settings:
    """Aggregated settings container.

    Instantiate once per process.  Use :func:`get_settings` to obtain a
    cached singleton so that .env is only parsed once.
    """

    def __init__(self) -> None:
        self.polar = PolarSettings()
        self.storage = StorageSettings()
        self.app = AppSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
