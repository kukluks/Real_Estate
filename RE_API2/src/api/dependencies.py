from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_maker
from src.services.property import PropertyService


async def get_db():
    async with async_session_maker() as session:
        yield session


def get_service(db: AsyncSession = Depends(get_db)):  # noqa: B008
    return PropertyService(db)
