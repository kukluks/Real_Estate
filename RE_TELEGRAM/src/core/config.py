import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Без токена/chat_id сервис бессмысленен, поэтому это обязательные поля (без default) —
    # лучше упасть при старте контейнера, чем молча не отправлять уведомления.
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str

    # Адрес RE_PARSER для команды /add_source, например http://re_parser_api:8001/sources.
    # Не задан — команда /add_source просто ответит, что не настроена.
    SOURCE_API_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('MODE', 'dev')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
