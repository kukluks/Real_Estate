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
    # Как часто monitor loop стартует новый обход (секунды).
    # 120 — разумный компромисс: быстрее, чем 300, но не долбит Instagram каждую минуту.
    MONITOR_INTERVAL_SECONDS: int = 120
    # Сколько Instagram-профилей парсить одновременно.
    # 1 = как раньше (последовательно). 2–3 — нормальный старт. Выше 3 — риск бана/RAM.
    SCRAPE_CONCURRENCY: int = 3

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

    # Адрес RE_TELEGRAM, например http://re_telegram:8002/notify.
    TELEGRAM_NOTIFY_URL: str | None = None
    # Адрес RE_AI, например http://re_ai:8003/extract.
    AI_EXTRACT_URL: str | None = None
    # Адрес RE_API2, например http://re_api_app:8000/properties/.
    PROPERTY_API_URL: str | None = None

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
            "AI_EXTRACT_URL",
            "PROPERTY_API_URL",
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
