from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repository import RawPostRepository
from src.schemas.raw_post import RawPostAddSchema


class RawPostService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repository = RawPostRepository(db_session)

    async def add_raw_post(self, raw_post_data: RawPostAddSchema):
        return await self.repository.add_raw_post(raw_post_data)

    async def save_raw_posts(self, raw_posts: list[RawPostAddSchema]) -> int:
        saved_count = 0
        for raw_post in raw_posts:
            await self.add_raw_post(raw_post)
            saved_count += 1
        return saved_count

    async def get_raw_posts(self):
        return await self.repository.get_raw_posts()
