import base64
import json

import httpx

from src.core.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# strict:true требует, чтобы ВСЕ поля были в required и additionalProperties=false —
# поэтому необязательные по смыслу поля описаны как ["<тип>", "null"], а не через .get()/default.
EXTRACTION_SCHEMA = {
    "name": "property_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Короткое человекочитаемое название объявления, одна строка",
            },
            "price": {
                "type": ["number", "null"],
                "description": "Цена как число, без символов валюты. null, если цена не указана",
            },
            "currency_note": {
                "type": ["string", "null"],
                "description": "Валюта и нюансы цены (торг, обмен на авто и т.п.), если есть",
            },
            "rooms": {
                "type": ["integer", "null"],
                "description": "Число комнат, если указано в тексте",
            },
            "area_sqm": {
                "type": ["number", "null"],
                "description": "Площадь в квадратных метрах, если указана",
            },
            "city": {
                "type": "string",
                "description": "Город. 'unknown', если не удалось определить",
            },
            "district": {
                "type": ["string", "null"],
                "description": "Район, улица или адрес, если указан",
            },
            "property_type": {
                "type": "string",
                "description": "Тип объекта: квартира, дом, помещение, гараж и т.п. 'unknown', если непонятно",
            },
            "contact": {
                "type": ["string", "null"],
                "description": "Номер телефона или иной контакт, если указан в тексте",
            },
            "ai_notes": {
                "type": ["string", "null"],
                "description": "Короткое (1-2 предложения) замечание по фото или тексту: состояние, "
                "подозрительные детали, что стоит уточнить у продавца",
            },
        },
        "required": [
            "title",
            "price",
            "currency_note",
            "rooms",
            "area_sqm",
            "city",
            "district",
            "property_type",
            "contact",
            "ai_notes",
        ],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "Ты помогаешь риелтору разбирать объявления о недвижимости из Instagram. "
    "Тебе дают подпись к посту (может быть на русском или кыргызском) и, возможно, фото. "
    "Извлеки структурированные данные строго по схеме. Если что-то не указано в тексте — "
    "используй null (или 'unknown' для city/property_type). Не выдумывай цифры, которых нет "
    "в подписи. Цену указывай числом без символов валюты, а валюту и любые нюансы (торг, "
    "обмен) — отдельно в currency_note."
)


class GroqExtractionError(Exception):
    pass


class GroqClient:
    def __init__(self) -> None:
        self._api_key = settings.GROQ_API_KEY
        self._model = settings.GROQ_MODEL

    async def extract(self, caption: str, image_bytes: bytes | None, image_content_type: str) -> dict:
        content: list[dict] = [{"type": "text", "text": f"Подпись к посту:\n{caption or '(подписи нет)'}"}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_content_type};base64,{b64}"},
                }
            )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_schema", "json_schema": EXTRACTION_SCHEMA},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(GROQ_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            raw_text = data["choices"][0]["message"]["content"]
            return json.loads(raw_text)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise GroqExtractionError(f"Unexpected Groq response shape: {e}. Raw: {data}") from e
