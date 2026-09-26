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
        media_paths: str | None,
    ) -> None:
        if not self.enabled:
            return

        data = {
            "profile_username": profile_username,
            "post_url": post_url,
            "caption": caption or "",
        }

        # media_paths — все файлы карусели/видео, скачанные парсером, а не только одна превью-картинка
        paths = [p for p in (media_paths or "").split("\n") if p and Path(p).exists()]

        try:
            if paths:
                open_files = [Path(p).open("rb") for p in paths]
                try:
                    files = [
                        ("media", (Path(p).name, f, "application/octet-stream"))
                        for p, f in zip(paths, open_files)
                    ]
                    async with httpx.AsyncClient(timeout=90.0) as client:
                        response = await client.post(self._url, data=data, files=files)
                finally:
                    for f in open_files:
                        f.close()
            else:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(self._url, data=data)
            response.raise_for_status()
        except Exception as e:
            print(f"Notify service call failed for {post_url}: {e}")
