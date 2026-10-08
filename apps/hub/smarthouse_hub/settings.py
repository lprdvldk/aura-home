from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Override with SMART_HOUSE_* env vars or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="SMART_HOUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    house_config: Path = Field(default=Path("config/house.json"))
    data_dir: Path = Field(default=Path("data/users"))
    http_host: str = "0.0.0.0"
    http_port: int = 18443
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 18551
    cors_origins: str = "*"
    session_hours: int = 12

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings() -> Settings:
    return Settings()
