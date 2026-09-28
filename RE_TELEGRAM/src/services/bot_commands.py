import asyncio

import httpx

from src.clients.telegram import TelegramClient
from src.core.config import settings
from src.services.recipients import RecipientStore

TELEGRAM_API_URL = "https://api.telegram.org"
POLL_ERROR_BACKOFF_SECONDS = 3
LONG_POLL_TIMEOUT_SECONDS = 25  # long polling: getUpdates сам держит соединение до этого таймаута

SOURCE_COMMANDS_HELP = (
    "/add_source <instagram_username> — добавить источник\n"
    "/my_sources — мои источники\n"
    "/remove_source <instagram_username> — удалить мой источник"
)
ADMIN_HELP_TEXT = (
    "Команды владельца:\n"
    f"{SOURCE_COMMANDS_HELP}\n"
    "/approve <chat_id> — одобрить доступ пользователю\n"
    "/revoke <chat_id> — забрать доступ (и удалить его источники)\n"
    "/list_users — список одобренных получателей"
)
VIEWER_HELP_TEXT = f"Команды:\n{SOURCE_COMMANDS_HELP}"


class BotCommandListener:
    """
    Слушает входящие сообщения боту через getUpdates (long polling) — без вебхука и без
    публичного URL, подходит для локальной разработки.

    Три категории отправителей:
    - admin (TELEGRAM_CHAT_ID из .env) — источники + управление доступом;
    - одобренные получатели — свои источники (/add_source, /my_sources, /remove_source);
    - все остальные — при первом сообщении это трактуется как заявка на доступ, админу
      уходит запрос с готовой командой /approve <chat_id>.

    Каждый видит и получает уведомления только по тем источникам, которые добавил сам.
    """

    def __init__(self) -> None:
        self._token = settings.TELEGRAM_BOT_TOKEN
        self._admin_chat_id = str(settings.TELEGRAM_CHAT_ID)
        self._offset: int | None = None
        self._telegram = TelegramClient()
        self._recipients = RecipientStore(self._admin_chat_id)

    async def run_forever(self) -> None:
        while True:
            try:
                updates = await self._get_updates()
            except Exception as e:
                print(f"Bot polling error: {e}")
                await asyncio.sleep(POLL_ERROR_BACKOFF_SECONDS)
                continue

            for update in updates:
                try:
                    await self._handle_update(update)
                except Exception as e:
                    print(f"Failed to handle update {update.get('update_id')}: {e}")

    async def _get_updates(self) -> list[dict]:
        url = f"{TELEGRAM_API_URL}/bot{self._token}/getUpdates"
        params = {"timeout": LONG_POLL_TIMEOUT_SECONDS}
        if self._offset is not None:
            params["offset"] = self._offset

        async with httpx.AsyncClient(timeout=LONG_POLL_TIMEOUT_SECONDS + 10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        updates = data.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    async def _handle_update(self, update: dict) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        username = chat.get("username")
        text = (message.get("text") or "").strip()

        if not text or not chat_id:
            return

        if self._recipients.is_admin(chat_id):
            await self._handle_admin_command(text)
        elif self._recipients.is_approved(chat_id):
            await self._handle_viewer_command(chat_id, text)
        else:
            await self._handle_access_request(chat_id, username)

    # ------------------------------------------------------------------ #
    # Диспетчеризация
    # ------------------------------------------------------------------ #
    async def _handle_admin_command(self, text: str) -> None:
        if await self._handle_source_command(self._admin_chat_id, text):
            return
        if text.startswith("/approve"):
            await self._handle_approve(text)
        elif text.startswith("/revoke"):
            await self._handle_revoke(text)
        elif text == "/list_users":
            approved = self._recipients.list_approved()
            body = "\n".join(approved) if approved else "(пока никого)"
            await self._telegram.send_text_to(self._admin_chat_id, f"Одобренные получатели:\n{body}")
        elif text in ("/start", "/help"):
            await self._telegram.send_text_to(self._admin_chat_id, ADMIN_HELP_TEXT)
        else:
            await self._telegram.send_text_to(self._admin_chat_id, f"Неизвестная команда.\n\n{ADMIN_HELP_TEXT}")

    async def _handle_viewer_command(self, chat_id: str, text: str) -> None:
        if await self._handle_source_command(chat_id, text):
            return
        if text in ("/start", "/help"):
            await self._telegram.send_text_to(chat_id, VIEWER_HELP_TEXT)
        else:
            await self._telegram.send_text_to(chat_id, f"Неизвестная команда.\n\n{VIEWER_HELP_TEXT}")

    async def _handle_source_command(self, chat_id: str, text: str) -> bool:
        """Команды про источники — общие для админа и одобренных. True, если команда обработана."""
        if text.startswith("/add_source"):
            await self._handle_add_source(text, chat_id)
        elif text.startswith("/my_sources"):
            await self._handle_my_sources(chat_id)
        elif text.startswith("/remove_source"):
            await self._handle_remove_source(text, chat_id)
        else:
            return False
        return True

    # ------------------------------------------------------------------ #
    # Доступ
    # ------------------------------------------------------------------ #
    async def _handle_access_request(self, chat_id: str, username: str | None) -> None:
        self._recipients.add_pending_request(chat_id, username)
        await self._telegram.send_text_to(chat_id, "Запрос на доступ отправлен владельцу. Ожидайте подтверждения.")
        who = f"@{username}" if username else f"chat_id={chat_id}"
        await self._telegram.send_text_to(
            self._admin_chat_id,
            f"Новый запрос доступа от {who}.\nРазрешить: /approve {chat_id}",
        )

    async def _handle_approve(self, text: str) -> None:
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._telegram.send_text_to(self._admin_chat_id, "Использование: /approve <chat_id>")
            return
        chat_id = parts[1].strip()
        self._recipients.approve(chat_id)
        await self._telegram.send_text_to(self._admin_chat_id, f"✅ Доступ выдан chat_id={chat_id}.")
        await self._telegram.send_text_to(
            chat_id,
            "✅ Вам открыт доступ. Добавьте источник: /add_source <instagram_username> — "
            "уведомления будут приходить только по вашим источникам.",
        )

    async def _handle_revoke(self, text: str) -> None:
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._telegram.send_text_to(self._admin_chat_id, "Использование: /revoke <chat_id>")
            return
        chat_id = parts[1].strip()
        self._recipients.revoke(chat_id)

        # Без этого источники отозванного продолжали бы скрапиться впустую (уведомления ему
        # уже не уходят, но браузер и ИИ тратились бы).
        removed = await self._remove_sources(chat_id)
        if removed is None:
            note = "Источники удалить не удалось (проверьте SOURCE_API_URL и RE_PARSER)."
        else:
            note = f"Удалено источников: {removed}."
        await self._telegram.send_text_to(self._admin_chat_id, f"Доступ отозван у chat_id={chat_id}. {note}")

    # ------------------------------------------------------------------ #
    # Источники (через API RE_PARSER)
    # ------------------------------------------------------------------ #
    async def _sources_api(self, method: str, **kwargs) -> httpx.Response:
        # Таймаут большой: при добавлении RE_PARSER реально открывает профиль в браузере.
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await client.request(method, settings.SOURCE_API_URL, **kwargs)

    async def _require_source_api(self, chat_id: str) -> bool:
        if settings.SOURCE_API_URL:
            return True
        await self._telegram.send_text_to(
            chat_id, "SOURCE_API_URL не настроен в RE_TELEGRAM — некуда отправлять запрос."
        )
        return False

    async def _remove_sources(self, chat_id: str) -> int | None:
        """Удаляет ВСЕ источники пользователя. None — если не удалось."""
        if not settings.SOURCE_API_URL:
            return None
        try:
            response = await self._sources_api("DELETE", params={"owner_chat_id": chat_id})
            response.raise_for_status()
            return int(response.json().get("deleted", 0))
        except Exception as e:
            print(f"Failed to remove sources of {chat_id}: {e}")
            return None

    async def _handle_add_source(self, text: str, chat_id: str) -> None:
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._telegram.send_text_to(chat_id, "Использование: /add_source <instagram_username>")
            return
        username = parts[1].strip().lstrip("@")

        if not await self._require_source_api(chat_id):
            return

        try:
            response = await self._sources_api(
                "POST",
                json={"profile_username": username, "added_by_chat_id": chat_id},
            )
        except Exception as e:
            await self._telegram.send_text_to(chat_id, f"Не удалось связаться с парсером: {e}")
            return

        if response.status_code == 200:
            await self._telegram.send_text_to(
                chat_id,
                f"✅ Источник @{username.lower()} добавлен. Парсер подхватит его на следующем цикле, "
                "перезапускать ничего не нужно.",
            )
        elif response.status_code == 404:
            await self._telegram.send_text_to(chat_id, f"❌ Профиль @{username} не найден в Instagram.")
        else:
            await self._telegram.send_text_to(
                chat_id, f"❌ Не удалось добавить @{username}: {self._error_detail(response)}"
            )

    async def _handle_my_sources(self, chat_id: str) -> None:
        if not await self._require_source_api(chat_id):
            return
        try:
            response = await self._sources_api("GET", params={"owner_chat_id": chat_id})
            response.raise_for_status()
            sources = response.json()
        except Exception as e:
            await self._telegram.send_text_to(chat_id, f"Не удалось получить список источников: {e}")
            return

        if not sources:
            await self._telegram.send_text_to(
                chat_id, "У вас пока нет источников. Добавьте: /add_source <instagram_username>"
            )
            return
        lines = "\n".join(f"@{s['profile_username']}" for s in sources)
        await self._telegram.send_text_to(chat_id, f"Ваши источники:\n{lines}")

    async def _handle_remove_source(self, text: str, chat_id: str) -> None:
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._telegram.send_text_to(chat_id, "Использование: /remove_source <instagram_username>")
            return
        username = parts[1].strip().lstrip("@")

        if not await self._require_source_api(chat_id):
            return
        try:
            response = await self._sources_api(
                "DELETE",
                params={"owner_chat_id": chat_id, "profile_username": username},
            )
        except Exception as e:
            await self._telegram.send_text_to(chat_id, f"Не удалось связаться с парсером: {e}")
            return

        if response.status_code == 200:
            await self._telegram.send_text_to(
                chat_id, f"🗑 Источник @{username.lower()} удалён, уведомления по нему больше не придут."
            )
        elif response.status_code == 404:
            await self._telegram.send_text_to(chat_id, f"У вас нет источника @{username}.")
        else:
            await self._telegram.send_text_to(
                chat_id, f"❌ Не удалось удалить @{username}: {self._error_detail(response)}"
            )

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            return str(response.json().get("detail", response.text))
        except Exception:
            return response.text
