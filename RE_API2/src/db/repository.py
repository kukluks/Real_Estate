from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.property import PropertyModel
from src.schemas.property import PropertyAddSchema


class PropertyRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_property(self, property_data: PropertyAddSchema) -> PropertyModel:
        existing_property = await self.get_property_by_url(str(property_data.url))
        if existing_property is not None:
            existing_property.title = property_data.title
            existing_property.description = property_data.description
            existing_property.price = property_data.price
            existing_property.source = property_data.source
            existing_property.city = property_data.city
            existing_property.property_type = property_data.property_type
            existing_property.external_id = property_data.external_id
            existing_property.contact = property_data.contact

            await self.db_session.commit()
            await self.db_session.refresh(existing_property)
            return existing_property

        property_model = PropertyModel(
            title=property_data.title,
            description=property_data.description,
            price=property_data.price,
            url=str(property_data.url),
            source=property_data.source,
            city=property_data.city,
            property_type=property_data.property_type,
            external_id=property_data.external_id,
            contact=property_data.contact,
        )
        self.db_session.add(property_model)
        await self.db_session.commit()
        await self.db_session.refresh(property_model)
        return property_model

    async def get_property_by_url(self, url: str) -> PropertyModel | None:
        query = select(PropertyModel).where(PropertyModel.url == url)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_properties(self) -> list[PropertyModel]:
        query = select(PropertyModel).order_by(PropertyModel.id.desc())
        result = await self.db_session.execute(query)
        return list(result.scalars().all())
