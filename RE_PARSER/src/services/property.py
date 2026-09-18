import json

import httpx

from src.core.config import settings
from src.parsers.registry import get_parser
from src.schemas.property import PropertySchema


class PropertyService:
    def __init__(self) -> None:
        self.parser = get_parser()

    async def collect_properties(self, profile_username: str) -> list[PropertySchema]:
        return await self.parser.parse(profile_username)

    async def send_properties(self, properties: list[PropertySchema]) -> None:
        if not properties:
            print("No posts were parsed.")
            return

        if not settings.API_BASE_URL:
            print(
                json.dumps(
                    [item.model_dump(mode="json") for item in properties],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        async with httpx.AsyncClient(base_url=str(settings.API_BASE_URL), timeout=30.0) as client:
            for item in properties:
                response = await client.post("/properties/", json=item.model_dump(mode="json"))
                response.raise_for_status()

        print(f"Sent {len(properties)} posts to API.")
