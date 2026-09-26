from pathlib import Path

import httpx

from src.core.config import settings


class TelegramNotifier:
    """
    Не ходит в Telegram напрямую — шлёт multipart-запрос в отдельный сервис RE_TELEGRAM
    (POST /notify), который уже сам знает токен бота и chat_id. RE_PARSER про Telegram
    вообще ничего не знает, только про URL.

    Если TELEGRAM_NOTIFY_URL не задан — ничего не делает; недоступный RE_TELEGRAM тоже
    не должен ронять парсинг, поэтому все ошибки тут гасятся и только логируются.
    """

    def __init__(self) -> None:
        self._url = settings.TELEGRAM_NOTIFY_URL

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    async def notify_new_post(
        self,
        *,
        profile_username: str,
        post_url: str,
        caption: str | None,
        thumbnail_path: str | None,
    ) -> None:
        if not self.enabled:
            return

        data = {
            "profile_username": profile_username,
            "post_url": post_url,
            "caption": caption or "",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                path = Path(thumbnail_path) if thumbnail_path else None
                if path is not None and path.exists():
                    with path.open("rb") as file:
                        files = {"photo": (path.name, file, "image/jpeg")}
                        response = await client.post(self._url, data=data, files=files)
                else:
                    response = await client.post(self._url, data=data)
                response.raise_for_status()
        except Exception as e:
            print(f"Notify service call failed for {post_url}: {e}")
