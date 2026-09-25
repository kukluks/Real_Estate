import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.parsers.registry import get_parser
from src.schemas.raw_post import RawPostAddSchema
from src.services.raw_post import RawPostService
from src.services.source import SourceService


class PropertyService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self.parser = get_parser()
        self.raw_post_service = RawPostService(db_session)
        self.source_service = SourceService(db_session)

    async def collect_properties(self, profile_username: str) -> list[RawPostAddSchema]:
        # known_ids вместо since: парсер не открывает страницы уже сохранённых постов вообще
        known_ids = await self.raw_post_service.get_known_external_ids(profile_username)
        return await self.parser.parse(profile_username, known_external_ids=known_ids)

    async def parse_one(self, profile_username: str) -> int:
        """Разовый парсинг по запросу — используется эндпоинтом POST /parse."""
        raw_posts = await self.collect_properties(profile_username)
        return await self.raw_post_service.save_raw_posts(raw_posts)

    async def process_sources(self) -> None:
        sources = await self.source_service.get_active_sources()
        if not sources:
            print("No active sources found.")
            return

        total_saved = 0
        for source in sources:
            print(f"Processing source: {source.profile_username}")
            try:
                raw_posts = await self.collect_properties(source.profile_username)
                saved_count = await self.raw_post_service.save_raw_posts(raw_posts)
            except Exception as e:
                # Один упавший источник (login wall, бан, таймаут) не должен ронять весь цикл
                print(f"Source {source.profile_username} failed: {e}")
                await self.db_session.rollback()
                continue
            await self.source_service.update_last_checked_at(source.id)
            total_saved += saved_count
            print(f"Saved {saved_count} raw posts for source {source.profile_username}.")

        print(f"Saved {total_saved} raw posts in total.")

    async def dump_raw_posts(self) -> None:
        raw_posts = await self.raw_post_service.get_raw_posts()
        print(
            json.dumps(
                [
                    {
                        "id": item.id,
                        "source": item.source,
                        "profile_username": item.profile_username,
                        "external_id": item.external_id,
                        "post_url": item.post_url,
                        "ai_status": item.ai_status,
                    }
                    for item in raw_posts
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
