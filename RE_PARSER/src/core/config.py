import os
from typing import Any, Literal

from pydantic import AnyHttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MODE: Literal["dev", "test"] = "dev"

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

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_values(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        for key in [
            "API_BASE_URL",
            "INSTAGRAM_USERNAME",
            "INSTAGRAM_PASSWORD",
            "INSTAGRAM_SESSION_STATE_PATH",
        ]:
            if data.get(key) == "":
                data[key] = None

        return data


settings = Settings()  # type: ignore[call-arg]
