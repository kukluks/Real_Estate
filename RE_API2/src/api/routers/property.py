from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_service
from src.schemas.property import PropertyAddSchema, PropertyResponseSchema
from src.services.property import PropertyService

router = APIRouter(prefix="/properties", tags=["Properties"])


@router.post("/", response_model=PropertyResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_property_to_db(
    property_schema: PropertyAddSchema,
    property_service: PropertyService = Depends(get_service),  # noqa: B008
):
    return await property_service.add_property(property_schema)


@router.get("/", response_model=list[PropertyResponseSchema])
async def get_properties_from_db(
    property_service: PropertyService = Depends(get_service),  # noqa: B008
):
    return await property_service.get_properties()
