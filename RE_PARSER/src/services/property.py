import json

import httpx

from src.core.config import settings
from src.parsers.registry import get_parser
from src.schemas.property import PropertySchema


class PropertyService:
    def __init__(self) -> None:
        self.parser = get_parser(settings.PARSER_NAME)

    async def collect_properties(self) -> list[PropertySchema]:
        return await self.parser.parse()

    async def send_properties(self, properties: list[PropertySchema]) -> None:
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
                await client.post("/properties", json=item.model_dump(mode="json"))
