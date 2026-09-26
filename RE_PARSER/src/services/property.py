import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.telegram import TelegramNotifier
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
        self.notifier = TelegramNotifier()

    async def collect_properties(self, profile_username: str) -> list[RawPostAddSchema]:
<<<<<<< HEAD
        # known_ids вместо since: парсер не открывает страницы уже сохранённых постов вообще —
        # а значит, всё, что он вернул, гарантированно новое, и notify можно звать без доп. проверки в БД.
        known_ids = await self.raw_post_service.get_known_external_ids(profile_username)
        # execute() выше молча открыл транзакцию (autobegin). Закрываем её ЗДЕСЬ, до начала
        # долгого Playwright-парсинга — иначе транзакция висит открытой минуты подряд, соединение
        # в пуле может протухнуть, и следующий DB-вызов падает с непонятной ошибкой SQLAlchemy.
        await self.db_session.commit()
        return await self.parser.parse(profile_username, known_external_ids=known_ids)

    async def _notify_new_posts(self, raw_posts: list[RawPostAddSchema]) -> None:
        for post in raw_posts:
            await self.notifier.notify_new_post(
                profile_username=post.profile_username,
                post_url=str(post.post_url),
                caption=post.raw_caption,
                thumbnail_path=post.thumbnail_path,
            )

    async def parse_one(self, profile_username: str) -> int:
        """Разовый парсинг по запросу — используется эндпоинтом POST /parse."""
        raw_posts = await self.collect_properties(profile_username)
        saved_count = await self.raw_post_service.save_raw_posts(raw_posts)
        await self._notify_new_posts(raw_posts)
        return saved_count
=======
        # known_ids вместо since: парсер не открывает страницы уже сохранённых постов вообще
        known_ids = await self.raw_post_service.get_known_external_ids(profile_username)
        return await self.parser.parse(profile_username, known_external_ids=known_ids)

    async def parse_one(self, profile_username: str) -> int:
        """Разовый парсинг по запросу — используется эндпоинтом POST /parse."""
        raw_posts = await self.collect_properties(profile_username)
        return await self.raw_post_service.save_raw_posts(raw_posts)
>>>>>>> aab01c9d6a6eb5ba3b3418fc46f841b618592857

    async def process_sources(self) -> None:
        sources = await self.source_service.get_active_sources()
        await self.db_session.commit()  # см. комментарий в collect_properties
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
                try:
                    await self.db_session.rollback()
                except Exception as rollback_error:
                    print(f"Rollback also failed, session is likely dead: {rollback_error}")
                continue

            await self._notify_new_posts(raw_posts)
=======
                await self.db_session.rollback()
                continue
>>>>>>> aab01c9d6a6eb5ba3b3418fc46f841b618592857
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
