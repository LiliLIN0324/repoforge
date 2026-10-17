"""Configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    nebius_api_key: str = Field(default="", alias="NEBIUS_API_KEY")
    nebius_base_url: str = Field(
        default="https://api.tokenfactory.nebius.com/v1/",
        alias="NEBIUS_BASE_URL",
    )

    nebius_model_nano: str = Field(
        default="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        alias="NEBIUS_MODEL_NANO",
    )
    nebius_model_super: str = Field(
        default="nvidia/nemotron-3-super-120b-a12b",
        alias="NEBIUS_MODEL_SUPER",
    )
    nebius_model_ultra: str = Field(
        default="nvidia/Nemotron-3-Ultra-550b-a55b",
        alias="NEBIUS_MODEL_ULTRA",
    )

    dry_run: bool = Field(default=True, alias="REPOFORGE_DRY_RUN")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    host: str = Field(default="127.0.0.1", alias="REPOFORGE_HOST")
    port: int = Field(default=8000, alias="REPOFORGE_PORT")

    max_iterations: int = 8
    default_tier: Literal["nano", "super", "ultra"] = "nano"

    def model_for(self, tier: Literal["nano", "super", "ultra"]) -> str:
        return {
            "nano": self.nebius_model_nano,
            "super": self.nebius_model_super,
            "ultra": self.nebius_model_ultra,
        }[tier]

    @property
    def has_api_key(self) -> bool:
        return bool(self.nebius_api_key.strip())

    @property
    def use_mock(self) -> bool:
        """True when dry-run is on or no API key is configured."""
        return self.dry_run or not self.has_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
