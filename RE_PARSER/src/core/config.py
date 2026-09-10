import os
from typing import Literal

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MODE: Literal["dev", "test"] = "dev"

    START_URL: AnyHttpUrl
    HEADLESS: bool = True
    BROWSER: Literal["chromium", "firefox", "webkit"] = "chromium"
    TIMEOUT_MS: int = 30_000
    MAX_ITEMS: int = 20

    API_BASE_URL: AnyHttpUrl | None = None

    INSTAGRAM_USERNAME: str | None = None
    INSTAGRAM_PASSWORD: str | None = None
    INSTAGRAM_SESSION_STATE_PATH: str | None = None
    INSTAGRAM_SCROLL_COUNT: int = 3
    INSTAGRAM_LOGIN_REQUIRED: bool = False
    INSTAGRAM_SAVE_SESSION: bool = False

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('MODE', 'dev')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
