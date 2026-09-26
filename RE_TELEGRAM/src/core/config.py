import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Без токена/chat_id сервис бессмысленен, поэтому это обязательные поля (без default) —
    # лучше упасть при старте контейнера, чем молча не отправлять уведомления.
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('MODE', 'dev')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
