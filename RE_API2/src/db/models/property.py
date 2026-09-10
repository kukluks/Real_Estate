import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.models.mixins import ID_mixin


class PropertyModel(Base, ID_mixin):
    __tablename__ = "properties"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False, default="unknown")
    property_type: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
