from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.raw_post import RawPostModel
from src.schemas.raw_post import RawPostAddSchema


class RawPostRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add_raw_post(self, raw_post_data: RawPostAddSchema) -> RawPostModel:
        existing_post = await self.get_raw_post_by_external_id(raw_post_data.external_id)
        if existing_post is not None:
            existing_post.profile_username = raw_post_data.profile_username
            existing_post.post_url = str(raw_post_data.post_url)
            existing_post.raw_caption = raw_post_data.raw_caption
            existing_post.media_urls = raw_post_data.media_urls
            existing_post.thumbnail_url = (
                str(raw_post_data.thumbnail_url) if raw_post_data.thumbnail_url else None
            )
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
            raw_caption=raw_post_data.raw_caption,
            media_urls=raw_post_data.media_urls,
            thumbnail_url=str(raw_post_data.thumbnail_url) if raw_post_data.thumbnail_url else None,
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
