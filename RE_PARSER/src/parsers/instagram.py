import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import HttpUrl
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page

from src.clients.playwright import PlaywrightClient
from src.core.config import settings
from src.parsers.base import BasePropertyParser
from src.schemas.property import PropertySource
from src.schemas.raw_post import RawPostAddSchema


class InstagramPropertyParser(BasePropertyParser):
    @property
    def source_name(self) -> str:
        return PropertySource.INSTAGRAM.value

    async def parse(self, profile_username: str) -> list[RawPostAddSchema]:
        self._validate_settings()
        profile_url = self._build_profile_url(profile_username)

        print(f"Opening Instagram profile: {profile_username}")

        async with PlaywrightClient() as client:
            page = await client.new_page()
            await page.goto(profile_url, wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)
            await self._login_if_needed(page)

            if settings.INSTAGRAM_SAVE_SESSION and settings.INSTAGRAM_SESSION_STATE_PATH:
                await self._save_session_state(client)

            await page.goto(profile_url, wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)
            await self._scroll_feed(page)

            post_links = await self._collect_post_links(page)
            print(f"Found {len(post_links)} posts/reels on profile {profile_username}.")

            raw_posts: list[RawPostAddSchema] = []
            for post_url in post_links[: settings.MAX_ITEMS]:
                raw_post = await self._parse_post(client, profile_username, post_url)
                if raw_post is not None:
                    raw_posts.append(raw_post)

            print(f"Parsed {len(raw_posts)} posts from profile {profile_username}.")
            return raw_posts

    def _validate_settings(self) -> None:
        if settings.INSTAGRAM_LOGIN_REQUIRED:
            has_credentials = bool(settings.INSTAGRAM_USERNAME and settings.INSTAGRAM_PASSWORD)
            has_session = bool(settings.INSTAGRAM_SESSION_STATE_PATH)
            if not has_credentials and not has_session:
                raise ValueError(
                    "Instagram login is required. Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD, "
                    "or provide INSTAGRAM_SESSION_STATE_PATH."
                )

    def _build_profile_url(self, profile_username: str) -> str:
        normalized_username = profile_username.strip().lstrip("@").strip("/")
        if not normalized_username:
            raise ValueError("Instagram profile username cannot be empty.")
        return f"https://www.instagram.com/{normalized_username}/"

    async def _login_if_needed(self, page: Page) -> None:
        if await self._is_logged_in(page):
            return

        if not settings.INSTAGRAM_USERNAME or not settings.INSTAGRAM_PASSWORD:
            return

        print("Trying to log into Instagram...")

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
        print(f"Saved Instagram session to {session_path}.")

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

    async def _parse_post(
        self, client: PlaywrightClient, profile_username: str, post_url: str
    ) -> RawPostAddSchema | None:
        page = await client.new_page()
        try:
            await page.goto(post_url, wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)

            external_id = self._extract_external_id(post_url)
            if not external_id:
                return None

            caption = await self._extract_caption(page)
            post_title = self._extract_post_title(caption)
            media_urls = await self._extract_media_urls(page)
            thumbnail_url = await self._extract_thumbnail_url(page)
            published_at = await self._extract_published_at(page)
            media_paths = await self._download_media_files(external_id, media_urls)
            thumbnail_path = await self._download_thumbnail(external_id, thumbnail_url)

            return RawPostAddSchema(
                source=PropertySource.INSTAGRAM.value,
                profile_username=profile_username,
                external_id=external_id,
                post_url=HttpUrl(post_url),
                post_title=post_title,
                raw_caption=caption,
                media_urls=self._serialize_media_urls(media_urls),
                media_paths=self._serialize_media_urls(media_paths),
                thumbnail_url=HttpUrl(thumbnail_url) if thumbnail_url else None,
                thumbnail_path=thumbnail_path,
                published_at=published_at,
                ai_status="new",
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

    def _extract_post_title(self, caption: str | None) -> str | None:
        if not caption:
            return None
        normalized_caption = caption.strip()
        if not normalized_caption:
            return None
        return normalized_caption

    async def _extract_media_urls(self, page: Page) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        previous_snapshot: str | None = None

        for _ in range(20):
            current_urls = await self._collect_current_slide_media(page)
            for media_url in current_urls:
                if media_url in seen:
                    continue
                seen.add(media_url)
                urls.append(media_url)

            current_snapshot = "|".join(current_urls)
            moved = await self._go_to_next_slide(page, previous_snapshot=current_snapshot)
            if not moved:
                break

            previous_snapshot = current_snapshot
            await page.wait_for_timeout(800)

        if not urls:
            fallback_image = await page.locator("meta[property='og:image']").get_attribute("content")
            if fallback_image:
                urls.append(fallback_image)

        return urls

    async def _collect_current_slide_media(self, page: Page) -> list[str]:
        article = page.locator("article").first
        urls: list[str] = []
        seen: set[str] = set()

        image_locator = article.locator("img")
        image_count = await image_locator.count()
        for index in range(image_count):
            image = image_locator.nth(index)
            src = await image.get_attribute("src")
            alt = (await image.get_attribute("alt") or "").lower()
            if not src:
                continue
            if "profile picture" in alt or "фото профиля" in alt:
                continue
            if src in seen:
                continue
            seen.add(src)
            urls.append(src)

        video_locator = article.locator("video")
        video_count = await video_locator.count()
        for index in range(video_count):
            video = video_locator.nth(index)
            src = await video.get_attribute("src")
            if not src:
                continue
            if src in seen:
                continue
            seen.add(src)
            urls.append(src)

        return urls

    async def _go_to_next_slide(self, page: Page, previous_snapshot: str | None) -> bool:
        candidates = [
            page.locator("button[aria-label='Next']").first,
            page.locator("svg[aria-label='Next']").locator("xpath=ancestor::button[1]").first,
            page.get_by_role("button", name=re.compile("next|далее|следующее", re.IGNORECASE)).first,
        ]

        for button in candidates:
            try:
                if await button.count() == 0:
                    continue
                if not await button.is_visible(timeout=500):
                    continue

                await button.click()

                for _ in range(10):
                    await page.wait_for_timeout(300)
                    current_urls = await self._collect_current_slide_media(page)
                    current_snapshot = "|".join(current_urls)
                    if current_snapshot and current_snapshot != previous_snapshot:
                        return True
            except PlaywrightError:
                continue

        return False

    async def _extract_thumbnail_url(self, page: Page) -> str | None:
        og_image = await page.locator("meta[property='og:image']").get_attribute("content")
        if og_image:
            return og_image.strip()
        return None

    async def _extract_published_at(self, page: Page):
        datetime_value = await page.locator("time").first.get_attribute("datetime")
        if datetime_value:
            from datetime import datetime

            return datetime.fromisoformat(datetime_value.replace("Z", "+00:00"))
        return None

    async def _download_media_files(self, external_id: str, media_urls: list[str]) -> list[str]:
        saved_paths: list[str] = []
        if not media_urls:
            return saved_paths

        target_dir = Path("/app/storage/raw_posts") / external_id
        target_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            for index, media_url in enumerate(media_urls, start=1):
                file_extension = self._guess_extension(media_url, default=".jpg")
                file_path = target_dir / f"media_{index}{file_extension}"
                try:
                    response = await client.get(media_url)
                    response.raise_for_status()
                    file_path.write_bytes(response.content)
                    saved_paths.append(str(file_path))
                except Exception:
                    continue

        return saved_paths

    async def _download_thumbnail(self, external_id: str, thumbnail_url: str | None) -> str | None:
        if not thumbnail_url:
            return None

        target_dir = Path("/app/storage/raw_posts") / external_id
        target_dir.mkdir(parents=True, exist_ok=True)
        file_extension = self._guess_extension(thumbnail_url, default=".jpg")
        file_path = target_dir / f"thumbnail{file_extension}"

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                response = await client.get(thumbnail_url)
                response.raise_for_status()
                file_path.write_bytes(response.content)
                return str(file_path)
            except Exception:
                return None

    def _guess_extension(self, url: str, default: str) -> str:
        parsed_url = urlparse(url)
        suffix = Path(parsed_url.path).suffix
        if suffix:
            return suffix
        return default

    def _serialize_media_urls(self, media_urls: list[str]) -> str | None:
        if not media_urls:
            return None
        return "\n".join(media_urls)

    async def _get_text(self, locator: Locator) -> str | None:
        try:
            if await locator.count() == 0:
                return None
            text = (await locator.inner_text()).strip()
            return text or None
        except PlaywrightError:
            return None

    def _extract_external_id(self, post_url: str) -> str | None:
        match = re.search(r"/(?:p|reel)/([^/]+)/?", post_url)
        if match:
            return match.group(1)
        return None
