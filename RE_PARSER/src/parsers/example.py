from src.clients.playwright import PlaywrightClient
from src.core.config import settings
from src.parsers.base import BasePropertyParser
from src.schemas.property import PropertySchema, PropertySource


class ExamplePropertyParser(BasePropertyParser):
    @property
    def source_name(self) -> str:
        return PropertySource.EXAMPLE.value

    async def parse(self) -> list[PropertySchema]:
        async with PlaywrightClient() as client:
            page = await client.new_page()
            await page.goto(str(settings.START_URL))
            title = await page.title()

        return [
            PropertySchema(
                title=title,
                description="Example parsed property",
                price=None,
                url=str(settings.START_URL),
                source=PropertySource.EXAMPLE,
                city="unknown",
                property_type="unknown",
            )
        ]
