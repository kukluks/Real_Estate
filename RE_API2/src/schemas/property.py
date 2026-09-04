from pydantic import BaseModel, ConfigDict


class PropertyAddSchema(BaseModel):
    title: str
    description: str
    price: float
    url: str
    source: str
    city: str
    property_type: str


class PropertyResponseSchema(PropertyAddSchema):
    id: int
    title: str
    description: str
    price: float
    url: str
    source: str
    city: str
    property_type: str

    model_config = ConfigDict(from_attributes=True)
