import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.mixins import ID_mixin


class RawPostModel(Base, ID_mixin):
    __tablename__ = "raw_posts"

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_username: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    post_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    post_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_paths: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ai_status: Mapped[str] = mapped_column(String(50), nullable=False, default="new")
