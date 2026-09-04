from enum import StrEnum

from pydantic import BaseModel, HttpUrl


class PropertySource(StrEnum):
    EXAMPLE = "example"
    LALAFO = "lalafo"


class PropertySchema(BaseModel):
    title: str
    description: str = ""
    price: float | None = None
    url: HttpUrl
    source: PropertySource
    city: str
    property_type: str
