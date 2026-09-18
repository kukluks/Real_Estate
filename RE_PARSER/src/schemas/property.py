from enum import Enum

from pydantic import BaseModel, HttpUrl


class PropertySource(str, Enum):
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
