import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.raw_post import RawPostModel
from src.db.models.source import SourceModel
from src.schemas.raw_post import RawPostAddSchema
from src.schemas.source import SourceAddSchema


class RawPostRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_raw_post(self, raw_post_data: RawPostAddSchema) -> RawPostModel:
        existing_post = await self.get_raw_post_by_external_id(raw_post_data.external_id)
        if existing_post is not None:
            existing_post.profile_username = raw_post_data.profile_username
            existing_post.post_url = str(raw_post_data.post_url)
            existing_post.post_title = raw_post_data.post_title
            existing_post.raw_caption = raw_post_data.raw_caption
            existing_post.media_urls = raw_post_data.media_urls
            existing_post.media_paths = raw_post_data.media_paths
            existing_post.thumbnail_url = (
                str(raw_post_data.thumbnail_url) if raw_post_data.thumbnail_url else None
            )
            existing_post.thumbnail_path = raw_post_data.thumbnail_path
            existing_post.published_at = raw_post_data.published_at
            existing_post.ai_status = raw_post_data.ai_status

            await self.db_session.commit()
            await self.db_session.refresh(existing_post)
            return existing_post

        raw_post = RawPostModel(
            source=raw_post_data.source,
            profile_username=raw_post_data.profile_username,
            external_id=raw_post_data.external_id,
            post_url=str(raw_post_data.post_url),
            post_title=raw_post_data.post_title,
            raw_caption=raw_post_data.raw_caption,
            media_urls=raw_post_data.media_urls,
            media_paths=raw_post_data.media_paths,
            thumbnail_url=str(raw_post_data.thumbnail_url) if raw_post_data.thumbnail_url else None,
            thumbnail_path=raw_post_data.thumbnail_path,
            published_at=raw_post_data.published_at,
            ai_status=raw_post_data.ai_status,
        )
        self.db_session.add(raw_post)
        await self.db_session.commit()
        await self.db_session.refresh(raw_post)
        return raw_post

    async def get_raw_post_by_external_id(self, external_id: str) -> RawPostModel | None:
        query = select(RawPostModel).where(RawPostModel.external_id == external_id)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_raw_posts(self) -> list[RawPostModel]:
        query = select(RawPostModel).order_by(RawPostModel.id.desc())
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class SourceRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_source(self, source_data: SourceAddSchema) -> SourceModel:
        existing_source = await self.get_source_by_profile_username(source_data.profile_username)
        if existing_source is not None:
            existing_source.source_type = source_data.source_type
            existing_source.profile_url = str(source_data.profile_url) if source_data.profile_url else None
            existing_source.is_active = source_data.is_active
            existing_source.notes = source_data.notes

            await self.db_session.commit()
            await self.db_session.refresh(existing_source)
            return existing_source

        source = SourceModel(
            source_type=source_data.source_type,
            profile_username=source_data.profile_username,
            profile_url=str(source_data.profile_url) if source_data.profile_url else None,
            is_active=source_data.is_active,
            notes=source_data.notes,
        )
        self.db_session.add(source)
        await self.db_session.commit()
        await self.db_session.refresh(source)
        return source

    async def get_source_by_profile_username(self, profile_username: str) -> SourceModel | None:
        query = select(SourceModel).where(SourceModel.profile_username == profile_username)
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_sources(self) -> list[SourceModel]:
        query = (
            select(SourceModel)
            .where(SourceModel.is_active.is_(True))
            .order_by(SourceModel.id.asc())
        )
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def update_last_checked_at(self, source_id: int) -> None:
        source = await self.db_session.get(SourceModel, source_id)
        if source is None:
            return
        source.last_checked_at = datetime.datetime.now(datetime.timezone.utc)
        await self.db_session.commit()
