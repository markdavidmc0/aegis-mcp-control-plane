"""Platform Operational Configuration."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform environment configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENABLE_CODE_MODE: bool = True
    DATA_PLANE_URL: str = Field(
        default="http://data-plane:8001",
        validation_alias=AliasChoices("DATA_PLANE_URL", "DATA_PLANE_MCP_URL"),
    )
    DATA_PLANE_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        validation_alias=AliasChoices("DATA_PLANE_TIMEOUT_SECONDS", "SANDBOX_TIMEOUT_SECONDS"),
    )


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()


def resolve_tools_dir(explicit_path: str | Path | None = None) -> Path:
    """Resolve directory path containing tool implementations and catalog."""
    if explicit_path:
        return Path(explicit_path)
    if os.getenv("ARM_TOOLS_DIR"):
        return Path(os.environ["ARM_TOOLS_DIR"])
    return Path.cwd() / "examples" / "tools"
