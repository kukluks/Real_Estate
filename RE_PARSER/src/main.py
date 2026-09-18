import asyncio
import sys

from src.services.property import PropertyService


def ask_profile_username() -> str:
    print("Enter Instagram profile:", end=" ", flush=True)
    profile_username = sys.stdin.readline().strip()
    if not profile_username:
        raise ValueError("Instagram profile cannot be empty.")
    return profile_username


async def main() -> None:
    profile_username = ask_profile_username()
    service = PropertyService()
    properties = await service.collect_properties(profile_username)
    await service.send_properties(properties)


if __name__ == "__main__":
    asyncio.run(main())
