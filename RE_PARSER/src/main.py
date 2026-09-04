import asyncio

from src.services.property import PropertyService


async def main() -> None:
    service = PropertyService()
    properties = await service.collect_properties()
    await service.send_properties(properties)


if __name__ == "__main__":
    asyncio.run(main())
