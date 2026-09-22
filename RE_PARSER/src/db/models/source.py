import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.mixins import ID_mixin


class SourceModel(Base, ID_mixin):
    __tablename__ = "sources"

    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="instagram")
    profile_username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
