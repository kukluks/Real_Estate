import json
from pathlib import Path

import httpx

from src.core.config import settings

TELEGRAM_API_URL = "https://api.telegram.org"
CAPTION_LIMIT = 1024  # реальный лимит Telegram на подпись к фото/видео/альбому
TEXT_MESSAGE_LIMIT = 4096  # реальный лимит Telegram на обычное текстовое сообщение
MAX_GROUP_SIZE = 10  # реальный лимит Telegram на число элементов в одном альбоме
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


def is_video(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


def guess_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video/mp4"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".png":
        return "image/png"
    return "image/jpeg"


class TelegramClient:
    def __init__(self) -> None:
        self._token = settings.TELEGRAM_BOT_TOKEN
        self._chat_id = settings.TELEGRAM_CHAT_ID

    async def send_text(self, text: str) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text[:TEXT_MESSAGE_LIMIT]}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    async def send_photo(self, filename: str, content: bytes, caption: str) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/sendPhoto"
        data = {"chat_id": self._chat_id, "caption": caption[:CAPTION_LIMIT]}
        files = {"photo": (filename, content, guess_content_type(filename))}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()

    async def send_video(self, filename: str, content: bytes, caption: str) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/sendVideo"
        data = {"chat_id": self._chat_id, "caption": caption[:CAPTION_LIMIT]}
        files = {"video": (filename, content, guess_content_type(filename))}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()

    async def send_media_group(self, files: list[tuple[str, bytes]], caption: str) -> None:
        """files — список (filename, content). Фото и видео можно мешать в одном альбоме."""
        for chunk_start in range(0, len(files), MAX_GROUP_SIZE):
            chunk = files[chunk_start : chunk_start + MAX_GROUP_SIZE]

            media_payload = []
            multipart_files = {}
            for index, (filename, content) in enumerate(chunk):
                field_name = f"file{index}"
                item: dict[str, str] = {
                    "type": "video" if is_video(filename) else "photo",
                    "media": f"attach://{field_name}",
                }
                if index == 0:
                    # Telegram показывает подпись только у первого элемента альбома
                    item["caption"] = caption[:CAPTION_LIMIT]
                media_payload.append(item)
                multipart_files[field_name] = (filename, content, guess_content_type(filename))

            url = f"{TELEGRAM_API_URL}/bot{self._token}/sendMediaGroup"
            data = {"chat_id": self._chat_id, "media": json.dumps(media_payload)}
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, data=data, files=multipart_files)
                response.raise_for_status()
