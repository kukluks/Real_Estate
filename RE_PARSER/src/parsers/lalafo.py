import re

from playwright.async_api import Locator, Page

from src.clients.playwright import PlaywrightClient
from src.core.config import settings
from src.parsers.base import BasePropertyParser
from src.schemas.property import PropertySchema, PropertySource


class LalafoPropertyParser(BasePropertyParser):
    @property
    def source_name(self) -> str:
        return PropertySource.LALAFO.value

    async def parse(self) -> list[PropertySchema]:
        async with PlaywrightClient() as client:
            page = await client.new_page()
            await page.goto(str(settings.START_URL), wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            await self._close_cookie_banner(page)

            cards = page.locator("a[href*='/']").filter(has=page.locator("h1, h2, h3, h4, [data-testid*='title']"))
            count = min(await cards.count(), settings.MAX_ITEMS)

            properties: list[PropertySchema] = []
            for index in range(count):
                card = cards.nth(index)
                property_item = await self._parse_card(card)
                if property_item is not None:
                    properties.append(property_item)

            return properties

    async def _parse_card(self, card: Locator) -> PropertySchema | None:
        href = await card.get_attribute("href")
        if not href:
            return None

        title = await self._extract_first_text(card, [
            "h1",
            "h2",
            "h3",
            "h4",
            "[data-testid*='title']",
            "[class*='title']",
        ])
        if not title:
            return None

        description = await self._extract_first_text(card, [
            "[data-testid*='description']",
            "[class*='description']",
            "p",
        ])
        price_text = await self._extract_first_text(card, [
            "[data-testid*='price']",
            "[class*='price']",
            "span",
            "div",
        ])
        city = await self._extract_first_text(card, [
            "[data-testid*='location']",
            "[class*='location']",
            "[class*='city']",
        ])
        property_type = await self._extract_property_type(title)

        return PropertySchema(
            title=title,
            description=description or "",
            price=self._extract_price(price_text),
            url=self._normalize_url(href),
            source=PropertySource.LALAFO,
            city=city or "unknown",
            property_type=property_type,
        )

    async def _close_cookie_banner(self, page: Page) -> None:
        buttons = [
            page.get_by_role("button", name=re.compile("accept|agree|ок|принять", re.IGNORECASE)),
            page.locator("button").filter(has_text=re.compile("accept|agree|ок|принять", re.IGNORECASE)),
        ]
        for button in buttons:
            try:
                if await button.first.is_visible(timeout=1_000):
                    await button.first.click()
                    return
            except Exception:
                continue

    async def _extract_first_text(self, card: Locator, selectors: list[str]) -> str | None:
        for selector in selectors:
            locator = card.locator(selector).first
            try:
                if await locator.count() == 0:
                    continue
                text = (await locator.inner_text()).strip()
                if text:
                    return text
            except Exception:
                continue
        return None

    async def _extract_property_type(self, title: str) -> str:
        normalized_title = title.lower()
        if "квартира" in normalized_title:
            return "apartment"
        if "дом" in normalized_title:
            return "house"
        if "участ" in normalized_title:
            return "land"
        return "unknown"

    def _extract_price(self, value: str | None) -> float | None:
        if not value:
            return None
        digits = re.findall(r"\d+[\d\s,.]*", value)
        if not digits:
            return None
        normalized = digits[0].replace(" ", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None

    def _normalize_url(self, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return f"https://lalafo.kg{href}"
