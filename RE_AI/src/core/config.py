import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str
    # llama-4-scout: быстрая и дешёвая (в бесплатном тире), умеет и vision, и строгий json_schema
    # одновременно — то, что нужно. llama-4-maverick можно указать сюда же, если понадобится
    # качество получше (она крупнее и медленнее), без изменений в остальном коде.
    GROQ_MODEL: str = "qwen/qwen3.8-27b"

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('MODE', 'dev')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
