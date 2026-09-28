import asyncio
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
MAX_SEND_ATTEMPTS = 3  # повторы при 429 (flood control), например при двух альбомах подряд
MAX_RETRY_WAIT_SECONDS = 30

ADMIN_COMMANDS = [
    {"command": "add_source", "description": "Добавить источник Instagram"},
    {"command": "my_sources", "description": "Мои источники"},
    {"command": "remove_source", "description": "Удалить мой источник"},
    {"command": "approve", "description": "Одобрить доступ пользователю (chat_id)"},
    {"command": "revoke", "description": "Забрать доступ у пользователя (chat_id)"},
    {"command": "list_users", "description": "Список одобренных получателей"},
    {"command": "help", "description": "Список команд"},
]
VIEWER_COMMANDS = [
    {"command": "add_source", "description": "Добавить источник Instagram"},
    {"command": "my_sources", "description": "Мои источники"},
    {"command": "remove_source", "description": "Удалить мой источник"},
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

    def _recipients_for(self, target_chat_id: str | None) -> list[str]:
        if target_chat_id:
            # Адресная доставка: только владелец источника (если он ещё approved / админ).
            if self._recipients.is_approved(target_chat_id):
                return [target_chat_id]
            print(f"target_chat_id={target_chat_id} is not approved, skip notify")
            return []
        # Без адресата (старый источник без владельца, ручной POST /parse) — только админу.
        # Раньше тут была рассылка ВСЕМ одобренным, что ломало правило «видишь только свои посты».
        return [self._recipients.admin_chat_id]

    async def _broadcast(
        self,
        send_one: Callable[[str], Awaitable[None]],
        target_chat_id: str | None = None,
    ) -> None:
        """Шлёт получателям; один недоступный (заблокировал бота и т.п.) не мешает остальным."""
        for chat_id in self._recipients_for(target_chat_id):
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
    # Низкоуровневый POST в Bot API с повтором при flood control (429).
    # ------------------------------------------------------------------ #
    @staticmethod
    def _retry_after(response: httpx.Response) -> int:
        try:
            return int(response.json()["parameters"]["retry_after"])
        except Exception:
            return 5

    async def _post(self, method: str, *, timeout: float, **kwargs) -> None:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/{method}"
        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, **kwargs)
            if response.status_code == 429 and attempt < MAX_SEND_ATTEMPTS:
                wait = min(self._retry_after(response), MAX_RETRY_WAIT_SECONDS)
                print(f"Telegram flood control on {method}, retry in {wait}s (attempt {attempt})")
                await asyncio.sleep(wait)
                continue
            response.raise_for_status()
            return

    # ------------------------------------------------------------------ #
    # Точечная отправка конкретному chat_id — для ответов на команды,
    # заявок на доступ и т.п. Не рассылка, а именно 1:1.
    # ------------------------------------------------------------------ #
    async def send_text_to(self, chat_id: str, text: str) -> None:
        await self._post(
            "sendMessage",
            timeout=15.0,
            json={"chat_id": chat_id, "text": text[:TEXT_MESSAGE_LIMIT]},
        )

    # ------------------------------------------------------------------ #
    # Рассылка: либо всем approved, либо только target_chat_id.
    # ------------------------------------------------------------------ #
    async def send_text(self, text: str, target_chat_id: str | None = None) -> None:
        await self._broadcast(
            lambda chat_id: self.send_text_to(chat_id, text),
            target_chat_id=target_chat_id,
        )

    async def send_photo(
        self,
        filename: str,
        content: bytes,
        caption: str,
        target_chat_id: str | None = None,
    ) -> None:
        async def _send(chat_id: str) -> None:
            await self._post(
                "sendPhoto",
                timeout=30.0,
                data={"chat_id": chat_id, "caption": caption[:CAPTION_LIMIT]},
                files={"photo": (filename, content, guess_content_type(filename))},
            )

        await self._broadcast(_send, target_chat_id=target_chat_id)

    async def send_video(
        self,
        filename: str,
        content: bytes,
        caption: str,
        target_chat_id: str | None = None,
    ) -> None:
        async def _send(chat_id: str) -> None:
            await self._post(
                "sendVideo",
                timeout=60.0,
                data={"chat_id": chat_id, "caption": caption[:CAPTION_LIMIT]},
                files={"video": (filename, content, guess_content_type(filename))},
            )

        await self._broadcast(_send, target_chat_id=target_chat_id)

    async def _send_chunk(
        self,
        chat_id: str,
        chunk: list[tuple[str, bytes]],
        caption: str | None,
    ) -> None:
        """Один альбом (2–10 файлов) или одиночный файл. caption=None — без подписи."""
        text = caption[:CAPTION_LIMIT] if caption else None

        if len(chunk) == 1:
            # Альбом в Telegram — минимум 2 элемента, поэтому остаток из одного файла
            # (например, 11-й) уходит обычным фото/видео.
            filename, content = chunk[0]
            method, field = ("sendVideo", "video") if is_video(filename) else ("sendPhoto", "photo")
            data = {"chat_id": chat_id}
            if text:
                data["caption"] = text
            await self._post(
                method,
                timeout=60.0,
                data=data,
                files={field: (filename, content, guess_content_type(filename))},
            )
            return

        media_payload = []
        multipart_files = {}
        for index, (filename, content) in enumerate(chunk):
            field_name = f"file{index}"
            item: dict[str, str] = {
                "type": "video" if is_video(filename) else "photo",
                "media": f"attach://{field_name}",
            }
            if index == 0 and text:
                # Telegram показывает подпись альбома по первому элементу, у которого она задана
                item["caption"] = text
            media_payload.append(item)
            multipart_files[field_name] = (filename, content, guess_content_type(filename))

        await self._post(
            "sendMediaGroup",
            timeout=120.0,
            data={"chat_id": chat_id, "media": json.dumps(media_payload)},
            files=multipart_files,
        )

    async def send_media_group(
        self,
        files: list[tuple[str, bytes]],
        caption: str,
        target_chat_id: str | None = None,
    ) -> None:
        """
        files — список (filename, content). Фото и видео можно мешать в одном альбоме.

        Больше 10 файлов режем на альбомы по 10. Подпись получает ТОЛЬКО последний кусок:
        сначала приходят 10 файлов без текста, потом остаток с текстом (текст оказывается
        внизу чата, где открывается переписка). Раньше подпись ставилась на каждый альбом,
        и текст дублировался.
        """
        chunks = [files[i : i + MAX_GROUP_SIZE] for i in range(0, len(files), MAX_GROUP_SIZE)]
        last = len(chunks) - 1

        async def _send(chat_id: str) -> None:
            for index, chunk in enumerate(chunks):
                is_last = index == last
                try:
                    await self._send_chunk(chat_id, chunk, caption if is_last else None)
                except Exception as e:
                    print(f"Failed to send album {index + 1}/{len(chunks)} to {chat_id}: {e}")
                    if is_last:
                        # Текст теперь в последнем сообщении — если оно не дошло, не теряем
                        # хотя бы сам текст.
                        await self.send_text_to(chat_id, caption)

        await self._broadcast(_send, target_chat_id=target_chat_id)
