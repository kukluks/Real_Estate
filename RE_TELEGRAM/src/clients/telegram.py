import httpx

from src.core.config import settings

TELEGRAM_API_URL = "https://api.telegram.org"
CAPTION_LIMIT = 1024  # ограничение самого Telegram на длину подписи к фото


class TelegramClient:
    def __init__(self) -> None:
        self._token = settings.TELEGRAM_BOT_TOKEN
        self._chat_id = settings.TELEGRAM_CHAT_ID

    async def send_text(self, text: str) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    async def send_photo(self, filename: str, content: bytes, caption: str) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/sendPhoto"
        data = {"chat_id": self._chat_id, "caption": caption[:CAPTION_LIMIT]}
        files = {"photo": (filename, content, "image/jpeg")}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()
