from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class RawPostAddSchema(BaseModel):
    source: str
    profile_username: str
    external_id: str
    post_url: HttpUrl
    post_title: str | None = None
    raw_caption: str | None = None
    media_urls: str | None = None
    media_paths: str | None = None
    thumbnail_url: HttpUrl | None = None
    thumbnail_path: str | None = None
    published_at: datetime | None = None
    ai_status: str = "new"


class RawPostResponseSchema(RawPostAddSchema):
    id: int
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)
