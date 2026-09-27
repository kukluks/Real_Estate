import httpx

from src.core.config import settings


class PropertyApiClient:
    """Best-effort сохранение в RE_API2. Не настроен/недоступен — просто пропускаем шаг."""

    def __init__(self) -> None:
        self._url = settings.PROPERTY_API_URL

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    async def upsert_property(self, payload: dict) -> None:
        if not self.enabled:
            return
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
        except Exception as e:
            print(f"Failed to save property to RE_API2: {e}")
