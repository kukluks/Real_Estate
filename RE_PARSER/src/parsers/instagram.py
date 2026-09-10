import re
from pathlib import Path
from urllib.parse import urljoin

from pydantic import HttpUrl
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page

from src.clients.playwright import PlaywrightClient
from src.core.config import settings
from src.parsers.base import BasePropertyParser
from src.schemas.property import PropertySchema, PropertySource


class InstagramPropertyParser(BasePropertyParser):
    @property
    def source_name(self) -> str:
        return PropertySource.INSTAGRAM.value

    async def parse(self) -> list[PropertySchema]:
        self._validate_settings()

        async with PlaywrightClient() as client:
            page = await client.new_page()
            await page.goto(str(settings.START_URL), wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)
            await self._login_if_needed(page)

            if settings.INSTAGRAM_SAVE_SESSION and settings.INSTAGRAM_SESSION_STATE_PATH:
                await self._save_session_state(client)

            await page.goto(str(settings.START_URL), wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)
            await self._scroll_feed(page)

            post_links = await self._collect_post_links(page)
            properties: list[PropertySchema] = []

            for post_url in post_links[: settings.MAX_ITEMS]:
                property_item = await self._parse_post(client, post_url)
                if property_item is not None:
                    properties.append(property_item)

            return properties

    def _validate_settings(self) -> None:
        if settings.INSTAGRAM_LOGIN_REQUIRED:
            has_credentials = bool(settings.INSTAGRAM_USERNAME and settings.INSTAGRAM_PASSWORD)
            has_session = bool(settings.INSTAGRAM_SESSION_STATE_PATH)
            if not has_credentials and not has_session:
                raise ValueError(
                    "Instagram login is required. Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD, "
                    "or provide INSTAGRAM_SESSION_STATE_PATH."
                )

    async def _login_if_needed(self, page: Page) -> None:
        if await self._is_logged_in(page):
            return

        if not settings.INSTAGRAM_USERNAME or not settings.INSTAGRAM_PASSWORD:
            return

        if "accounts/login" not in page.url:
            await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")

        username_input = page.locator("input[name='username']").first
        password_input = page.locator("input[name='password']").first
        await username_input.wait_for(state="visible")
        await password_input.wait_for(state="visible")
        await username_input.fill(settings.INSTAGRAM_USERNAME)
        await password_input.fill(settings.INSTAGRAM_PASSWORD)
        await page.locator("button[type='submit']").first.click()
        await page.wait_for_load_state("networkidle")
        await self._dismiss_dialogs(page)

    async def _save_session_state(self, client: PlaywrightClient) -> None:
        session_path = Path(settings.INSTAGRAM_SESSION_STATE_PATH or "")
        session_path.parent.mkdir(parents=True, exist_ok=True)
        await client.save_storage_state(str(session_path))

    async def _is_logged_in(self, page: Page) -> bool:
        selectors = [
            "a[href='/' ]",
            "a[href='/direct/inbox/']",
            "svg[aria-label='Home']",
            "nav",
        ]
        for selector in selectors:
            if await page.locator(selector).count() > 0:
                return True
        return False

    async def _dismiss_dialogs(self, page: Page) -> None:
        patterns = [
            re.compile("allow all cookies|разрешить все cookie|accept", re.IGNORECASE),
            re.compile("not now|не сейчас|later|сейчас нет", re.IGNORECASE),
        ]
        for pattern in patterns:
            candidates = [
                page.get_by_role("button", name=pattern),
                page.locator("button").filter(has_text=pattern),
            ]
            for candidate in candidates:
                try:
                    button = candidate.first
                    if await button.is_visible(timeout=1_000):
                        await button.click()
                        break
                except PlaywrightError:
                    continue

    async def _scroll_feed(self, page: Page) -> None:
        for _ in range(settings.INSTAGRAM_SCROLL_COUNT):
            await page.mouse.wheel(0, 5_000)
            await page.wait_for_timeout(1_500)

    async def _collect_post_links(self, page: Page) -> list[str]:
        anchors = page.locator("a[href*='/p/'], a[href*='/reel/']")
        count = await anchors.count()
        links: list[str] = []
        seen: set[str] = set()

        for index in range(count):
            href = await anchors.nth(index).get_attribute("href")
            if not href:
                continue
            normalized = urljoin("https://www.instagram.com", href)
            if normalized in seen:
                continue
            seen.add(normalized)
            links.append(normalized)

        return links

    async def _parse_post(self, client: PlaywrightClient, post_url: str) -> PropertySchema | None:
        page = await client.new_page()
        try:
            await page.goto(post_url, wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)

            caption = await self._extract_caption(page)
            if not caption:
                return None

            title = self._extract_title(caption)
            price = self._extract_price(caption)
            city = self._extract_city(caption)
            property_type = self._extract_property_type(caption)
            contact = self._extract_contact(caption)
            external_id = self._extract_external_id(post_url)

            return PropertySchema(
                title=title,
                description=caption,
                price=price,
                url=HttpUrl(post_url),
                source=PropertySource.INSTAGRAM,
                city=city,
                property_type=property_type,
                external_id=external_id,
                contact=contact,
            )
        finally:
            await page.close()

    async def _extract_caption(self, page: Page) -> str | None:
        selectors = [
            "article h1",
            "article ul li h1",
            "article ul li span",
            "article span[class]",
        ]
        for selector in selectors:
            text = await self._get_text(page.locator(selector).first)
            if text and len(text) > 10:
                return text

        meta_description = await page.locator("meta[property='og:description']").get_attribute("content")
        if meta_description:
            return meta_description.strip()

        return None

    async def _get_text(self, locator: Locator) -> str | None:
        try:
            if await locator.count() == 0:
                return None
            text = (await locator.inner_text()).strip()
            return text or None
        except PlaywrightError:
            return None

    def _extract_title(self, caption: str) -> str:
        first_line = caption.splitlines()[0].strip()
        if first_line:
            return first_line[:200]
        return "Instagram property"

    def _extract_price(self, value: str) -> float | None:
        matches = re.findall(r"(?:\$|€|сом|kgs|usd)?\s*\d[\d\s,.]{2,}", value, re.IGNORECASE)
        if not matches:
            return None
        normalized = re.sub(r"[^\d,.]", "", matches[0]).replace(" ", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return None

    def _extract_city(self, caption: str) -> str:
        cities = ["бишкек", "ош", "джалал-абад", "каракол", "иссык-куль", "jalal-abad"]
        normalized = caption.lower()
        for city in cities:
            if city in normalized:
                return city
        return "unknown"

    def _extract_property_type(self, caption: str) -> str:
        normalized = caption.lower()
        if "квартира" in normalized:
            return "apartment"
        if "дом" in normalized:
            return "house"
        if "участ" in normalized:
            return "land"
        if "офис" in normalized or "помещение" in normalized:
            return "commercial"
        return "unknown"

    def _extract_contact(self, caption: str) -> str | None:
        phone_match = re.search(r"(?:\+?996|0)\s*\(?\d{3}\)?[\s-]*\d{2}[\s-]*\d{2}[\s-]*\d{2}", caption)
        if phone_match:
            return phone_match.group(0)

        username_match = re.search(r"@[A-Za-z0-9._]+", caption)
        if username_match:
            return username_match.group(0)

        return None

    def _extract_external_id(self, post_url: str) -> str | None:
        match = re.search(r"/(?:p|reel)/([^/]+)/?", post_url)
        if match:
            return match.group(1)
        return None
