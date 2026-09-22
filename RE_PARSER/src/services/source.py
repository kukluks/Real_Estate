from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repository import SourceRepository
from src.schemas.source import SourceAddSchema


class SourceService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repository = SourceRepository(db_session)

    async def add_source(self, source_data: SourceAddSchema):
        return await self.repository.add_source(source_data)

    async def get_active_sources(self):
        return await self.repository.get_active_sources()

    async def update_last_checked_at(self, source_id: int) -> None:
        await self.repository.update_last_checked_at(source_id)
