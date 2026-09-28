import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str
    # Модель задаётся в .env (GROQ_MODEL); значение ниже — только запасное. Требования к модели:
    # понимать картинки (vision) и уметь отвечать по json_schema. Если модель без vision,
    # фото до неё не дойдёт и разбор будет идти только по тексту подписи.
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('MODE', 'dev')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore[call-arg]
