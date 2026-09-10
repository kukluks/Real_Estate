from enum import StrEnum

from pydantic import BaseModel, HttpUrl


class PropertySource(StrEnum):
    INSTAGRAM = "instagram"


class PropertySchema(BaseModel):
    title: str
    description: str = ""
    price: float | None = None
    url: HttpUrl
    source: PropertySource = PropertySource.INSTAGRAM
    city: str = "unknown"
    property_type: str = "unknown"
    external_id: str | None = None
    contact: str | None = None
