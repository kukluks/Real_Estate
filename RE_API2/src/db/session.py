from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.config import settings

# Engine С нулпулом нужен для тестов
engine = create_async_engine(
    settings.db_url, pool_size=5, max_overflow=10, pool_timeout=30
)
engine_null_pool = create_async_engine(
    settings.db_url, poolclass=NullPool
)


async_session_maker = async_sessionmaker(
    bind=engine, expire_on_commit=False
)
async_session_maker_null_pool = async_sessionmaker(
    bind=engine_null_pool, expire_on_commit=False
)
