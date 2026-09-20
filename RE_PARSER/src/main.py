import asyncio
import sys

from src.db.base import Base
from src.db.models.raw_post import RawPostModel  # noqa: F401
from src.db.session import async_session_maker, engine
from src.services.property import PropertyService


def ask_profile_username() -> str:
    print("Enter Instagram profile:", end=" ", flush=True)
    profile_username = sys.stdin.readline().strip()
    if not profile_username:
        raise ValueError("Instagram profile cannot be empty.")
    return profile_username


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    profile_username = ask_profile_username()
    async with async_session_maker() as session:
        service = PropertyService(session)
        properties = await service.collect_properties(profile_username)
        await service.save_properties(properties)


if __name__ == "__main__":
    asyncio.run(main())
