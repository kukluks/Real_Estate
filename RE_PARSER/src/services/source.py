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

    async def profile_is_tracked(self, profile_username: str) -> bool:
        """Профиль уже добавлен кем-то — значит, его существование уже проверялось."""
        return await self.repository.get_source_by_profile_username(profile_username) is not None

    async def list_by_owner(self, owner_chat_id: str):
        return await self.repository.list_by_owner(owner_chat_id)

    async def delete_sources(self, owner_chat_id: str, profile_username: str | None = None) -> int:
        return await self.repository.delete_sources(owner_chat_id, profile_username)

    async def update_last_checked_at(self, source_id: int) -> None:
        await self.repository.update_last_checked_at(source_id)
