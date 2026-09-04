from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, get_service
from src.schemas.property import PropertyAddSchema, PropertyResponseSchema
from src.services.property import PropertyService

router = APIRouter(prefix="/properties", tags=["Properties"])

@router.post("/", response_model=PropertyResponseSchema)
async def add_property_to_db(Property_schema: PropertyAddSchema, Property_Service: PropertyService = Depends(get_service), db: AsyncSession = Depends(get_db)):  # noqa: B008
    # Logic to add property to the database
    pass


@router.get("/", response_model=list[PropertyResponseSchema])
async def get_properties_from_db(Property_Service: PropertyService = Depends(get_service), db: AsyncSession = Depends(get_db)):  # noqa: B008
    # Logic to retrieve properties from the database
    pass
