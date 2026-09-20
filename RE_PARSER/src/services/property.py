import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.parsers.registry import get_parser
from src.schemas.raw_post import RawPostAddSchema
from src.services.raw_post import RawPostService


class PropertyService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self.parser = get_parser()
        self.raw_post_service = RawPostService(db_session)

    async def collect_properties(self, profile_username: str) -> list[RawPostAddSchema]:
        return await self.parser.parse(profile_username)

    async def save_properties(self, raw_posts: list[RawPostAddSchema]) -> None:
        if not raw_posts:
            print("No posts were parsed.")
            return

        saved_count = await self.raw_post_service.save_raw_posts(raw_posts)
        print(f"Saved {saved_count} raw posts to parser database.")
        print(json.dumps([item.model_dump(mode='json') for item in raw_posts], ensure_ascii=False, indent=2))
