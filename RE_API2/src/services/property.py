from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repository import PropertyRepository
from src.schemas.property import PropertyAddSchema


class PropertyService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repository = PropertyRepository(db_session)

    async def add_property(self, property_data: PropertyAddSchema):
        return await self.repository.add_property(property_data)

    async def get_properties(self):
        return await self.repository.get_properties()
