from pathlib import Path

import httpx

from src.core.config import settings


class AIClient:
    """
    Best-effort шаг: если RE_AI не настроен, недоступен или отвечает дольше таймаута —
    возвращаем None и НЕ бросаем исключение. Пост в этом случае просто уйдёт в Telegram
    без структуры (сырая подпись), а не потеряется вообще — извлечение цены/площади и т.п.
    вторично по отношению к самому факту уведомления.
    """

    def __init__(self) -> None:
        self._url = settings.AI_EXTRACT_URL

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    async def extract(self, *, caption: str | None, thumbnail_path: str | None) -> dict | None:
        if not self.enabled:
            return None

        data = {"caption": caption or ""}
        opened_file = None
        try:
            files = None
            if thumbnail_path and Path(thumbnail_path).exists():
                opened_file = Path(thumbnail_path).open("rb")
                files = {"image": (Path(thumbnail_path).name, opened_file, "image/jpeg")}

            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(self._url, data=data, files=files)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"AI extraction failed, falling back to raw caption: {e}")
            return None
        finally:
            if opened_file:
                opened_file.close()
