import asyncio
import sys

from src.db.base import Base
from src.db.models.raw_post import RawPostModel  # noqa: F401
from src.db.models.source import SourceModel  # noqa: F401
from src.db.session import async_session_maker, engine
from src.schemas.source import SourceAddSchema
from src.services.property import PropertyService
from src.services.source import SourceService


def ask_action() -> str:
    print("Choose action: [1] add source, [2] run parser, [3] show raw posts", end=" ", flush=True)
    action = sys.stdin.readline().strip()
    if action not in {"1", "2", "3"}:
        raise ValueError("Invalid action.")
    return action


def ask_profile_username() -> str:
    print("Enter Instagram profile:", end=" ", flush=True)
    profile_username = sys.stdin.readline().strip()
    if not profile_username:
        raise ValueError("Instagram profile cannot be empty.")
    return profile_username


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        action = ask_action()

        if action == "1":
            profile_username = ask_profile_username()
            source_service = SourceService(session)
            await source_service.add_source(
                SourceAddSchema(profile_username=profile_username)
            )
            print(f"Source {profile_username} saved.")
            return

        service = PropertyService(session)

        if action == "2":
            await service.process_sources()
            return

        if action == "3":
            await service.dump_raw_posts()
            return


if __name__ == "__main__":
    asyncio.run(main())
