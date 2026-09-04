import os
from typing import Literal

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.schemas.property import PropertySource


class Settings(BaseSettings):
    MODE: Literal["dev", "test"] = "dev"

    PARSER_NAME: PropertySource = PropertySource.EXAMPLE
    START_URL: AnyHttpUrl = "https://example.com"
    HEADLESS: bool = True
    BROWSER: Literal["chromium", "firefox", "webkit"] = "chromium"
    TIMEOUT_MS: int = 30_000
    MAX_ITEMS: int = 20

    API_BASE_URL: AnyHttpUrl | None = None

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('MODE', 'dev')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
