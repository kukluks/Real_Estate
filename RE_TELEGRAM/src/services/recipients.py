import json
from pathlib import Path

RECIPIENTS_FILE = Path("/app/data/recipients.json")


class RecipientStore:
    """
    Простое JSON-хранилище одобренных получателей уведомлений. RE_TELEGRAM сам по себе без
    БД, а список из нескольких chat_id не стоит того, чтобы тащить сюда Postgres. Файл лежит
    в уже примонтированной папке проекта (volume .:/app), поэтому переживает пересоздание
    контейнера.
    """

    def __init__(self, admin_chat_id: str) -> None:
        self._admin_chat_id = admin_chat_id
        RECIPIENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not RECIPIENTS_FILE.exists():
            RECIPIENTS_FILE.write_text(json.dumps({"approved": [], "pending": {}}))

    def _read(self) -> dict:
        return json.loads(RECIPIENTS_FILE.read_text())

    def _write(self, data: dict) -> None:
        RECIPIENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def all_recipients(self) -> list[str]:
        """Админ + все одобренные — все, кому шлём уведомления о новых постах."""
        data = self._read()
        return [self._admin_chat_id, *data["approved"]]

    def is_admin(self, chat_id: str) -> bool:
        return chat_id == self._admin_chat_id

    @property
    def admin_chat_id(self) -> str:
        return self._admin_chat_id

    def is_approved(self, chat_id: str) -> bool:
        return self.is_admin(chat_id) or chat_id in self._read()["approved"]

    def add_pending_request(self, chat_id: str, username: str | None) -> None:
        data = self._read()
        data["pending"][chat_id] = username or ""
        self._write(data)

    def approve(self, chat_id: str) -> None:
        data = self._read()
        if chat_id not in data["approved"]:
            data["approved"].append(chat_id)
        data["pending"].pop(chat_id, None)
        self._write(data)

    def revoke(self, chat_id: str) -> None:
        data = self._read()
        if chat_id in data["approved"]:
            data["approved"].remove(chat_id)
        self._write(data)

    def list_approved(self) -> list[str]:
        return self._read()["approved"]
