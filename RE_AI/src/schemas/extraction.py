from pydantic import BaseModel


class ExtractionResult(BaseModel):
    title: str
    price: float | None = None
    currency_note: str | None = None  # валюта, торг, обмен и т.п. — то, что не влезает в чистое число
    rooms: int | None = None
    area_sqm: float | None = None
    city: str = "unknown"
    district: str | None = None
    property_type: str = "unknown"
    contact: str | None = None
    ai_notes: str | None = None  # короткое замечание ИИ по фото/состоянию/тексту
