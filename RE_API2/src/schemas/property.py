from pydantic import BaseModel, ConfigDict, HttpUrl


class PropertyAddSchema(BaseModel):
    title: str
    description: str = ""
    price: float | None = None
    url: HttpUrl
    source: str
    city: str = "unknown"
    property_type: str = "unknown"
    external_id: str | None = None
    contact: str | None = None


class PropertyResponseSchema(PropertyAddSchema):
    id: int

    model_config = ConfigDict(from_attributes=True)
