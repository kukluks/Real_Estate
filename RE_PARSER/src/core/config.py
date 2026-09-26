import os
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MODE: Literal["dev", "test"] = "dev"

    HEADLESS: bool = True
    BROWSER: Literal["chromium", "firefox", "webkit"] = "chromium"
    TIMEOUT_MS: int = 30_000
    SAFETY_MAX_ITEMS: int = 100
    MONITOR_INTERVAL_SECONDS: int = 300

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    INSTAGRAM_USERNAME: str | None = None
    INSTAGRAM_PASSWORD: str | None = None
    INSTAGRAM_SESSION_STATE_PATH: str | None = None
    INSTAGRAM_SCROLL_COUNT: int = 3
    INSTAGRAM_LOGIN_REQUIRED: bool = False
    INSTAGRAM_SAVE_SESSION: bool = False

    # Адрес отдельного сервиса RE_TELEGRAM, например http://re_telegram:8002/notify.
    # Не задан — уведомления просто не шлются, парсинг работает как обычно.
    TELEGRAM_NOTIFY_URL: str | None = None

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
            "INSTAGRAM_USERNAME",
            "INSTAGRAM_PASSWORD",
            "INSTAGRAM_SESSION_STATE_PATH",
            "TELEGRAM_NOTIFY_URL",
        ]:
            if data.get(key) == "":
                data[key] = None

        return data

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()  # type: ignore[call-arg]
