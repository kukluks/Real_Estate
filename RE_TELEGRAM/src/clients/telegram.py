import json
from pathlib import Path
from typing import Awaitable, Callable

import httpx

from src.core.config import settings
from src.services.recipients import RecipientStore

TELEGRAM_API_URL = "https://api.telegram.org"
CAPTION_LIMIT = 1024  # реальный лимит Telegram на подпись к фото/видео/альбому
TEXT_MESSAGE_LIMIT = 4096  # реальный лимит Telegram на обычное текстовое сообщение
MAX_GROUP_SIZE = 10  # реальный лимит Telegram на число элементов в одном альбоме
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}

ADMIN_COMMANDS = [
    {"command": "add_source", "description": "Добавить источник Instagram"},
    {"command": "approve", "description": "Одобрить доступ пользователю (chat_id)"},
    {"command": "revoke", "description": "Забрать доступ у пользователя (chat_id)"},
    {"command": "list_users", "description": "Список одобренных получателей"},
    {"command": "help", "description": "Список команд"},
]
VIEWER_COMMANDS = [
    {"command": "add_source", "description": "Добавить источник Instagram"},
    {"command": "help", "description": "Список команд"},
]


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
        self._recipients = RecipientStore(str(settings.TELEGRAM_CHAT_ID))

    async def _broadcast(self, send_one: Callable[[str], Awaitable[None]]) -> None:
        """Шлёт всем одобренным получателям; один недоступный получатель (заблокировал бота
        и т.п.) не должен мешать остальным получить уведомление."""
        for chat_id in self._recipients.all_recipients():
            try:
                await send_one(chat_id)
            except Exception as e:
                print(f"Failed to notify chat_id {chat_id}: {e}")

    async def set_commands(self) -> None:
        """
        Регистрирует меню команд (иконка / рядом с полем ввода в Telegram). Без этого вызова
        у бота нет вообще никакого меню — Telegram не заполняет его автоматически по коду.
        Админу — полный список (управление доступом и источниками), остальным — только
        /add_source и /help. Best-effort: если Telegram недоступен на старте, просто не
        падаем — бот и без меню продолжит работать по текстовым командам.
        """
        url = f"{TELEGRAM_API_URL}/bot{self._token}/setMyCommands"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(url, json={"commands": VIEWER_COMMANDS})

                admin_chat_id = self._recipients.admin_chat_id
                scope_chat_id: int | str = (
                    int(admin_chat_id) if admin_chat_id.lstrip("-").isdigit() else admin_chat_id
                )
                await client.post(
                    url,
                    json={
                        "commands": ADMIN_COMMANDS,
                        "scope": {"type": "chat", "chat_id": scope_chat_id},
                    },
                )
        except Exception as e:
            print(f"Failed to register bot commands menu: {e}")

    # ------------------------------------------------------------------ #
    # Точечная отправка конкретному chat_id — для ответов на команды,
    # заявок на доступ и т.п. Не рассылка, а именно 1:1.
    # ------------------------------------------------------------------ #
    async def send_text_to(self, chat_id: str, text: str) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text[:TEXT_MESSAGE_LIMIT]}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    # ------------------------------------------------------------------ #
    # Рассылка всем одобренным получателям — уведомления о новых постах.
    # ------------------------------------------------------------------ #
    async def send_text(self, text: str) -> None:
        await self._broadcast(lambda chat_id: self.send_text_to(chat_id, text))

    async def send_photo(self, filename: str, content: bytes, caption: str) -> None:
        async def _send(chat_id: str) -> None:
            url = f"{TELEGRAM_API_URL}/bot{self._token}/sendPhoto"
            data = {"chat_id": chat_id, "caption": caption[:CAPTION_LIMIT]}
            files = {"photo": (filename, content, guess_content_type(filename))}
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()

        await self._broadcast(_send)

    async def send_video(self, filename: str, content: bytes, caption: str) -> None:
        async def _send(chat_id: str) -> None:
            url = f"{TELEGRAM_API_URL}/bot{self._token}/sendVideo"
            data = {"chat_id": chat_id, "caption": caption[:CAPTION_LIMIT]}
            files = {"video": (filename, content, guess_content_type(filename))}
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()

        await self._broadcast(_send)

    async def send_media_group(self, files: list[tuple[str, bytes]], caption: str) -> None:
        """files — список (filename, content). Фото и видео можно мешать в одном альбоме."""

        async def _send(chat_id: str) -> None:
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
                        item["caption"] = caption[:CAPTION_LIMIT]
                    media_payload.append(item)
                    multipart_files[field_name] = (filename, content, guess_content_type(filename))

                url = f"{TELEGRAM_API_URL}/bot{self._token}/sendMediaGroup"
                data = {"chat_id": chat_id, "media": json.dumps(media_payload)}
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(url, data=data, files=multipart_files)
                    response.raise_for_status()

        await self._broadcast(_send)
