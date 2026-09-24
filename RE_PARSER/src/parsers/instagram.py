import asyncio
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urljoin, urlparse

import httpx
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page, Response

from src.clients.playwright import PlaywrightClient
from src.core.config import settings
from src.parsers.base import BasePropertyParser
from src.schemas.property import PropertySource
from src.schemas.raw_post import RawPostAddSchema

INSTAGRAM_URL = "https://www.instagram.com"
STORAGE_DIR = Path("/app/storage/raw_posts")


class InstagramPropertyParser(BasePropertyParser):
    @property
    def source_name(self) -> str:
        return PropertySource.INSTAGRAM.value

    # ------------------------------------------------------------------ #
    # Главный сценарий
    # ------------------------------------------------------------------ #
    async def parse(
        self,
        profile_username: str,
        since: datetime | None = None,
        known_external_ids: set[str] | None = None,
    ) -> list[RawPostAddSchema]:
        """
        Возвращает только НОВЫЕ посты профиля.

        known_external_ids — shortcode'ы постов, которые уже есть в БД: их страницы мы вообще не открываем
        и медиа не качаем. Это надёжнее фильтра по дате: не зависит от закреплённых постов и от неудачных прогонов.
        Параметр since оставлен ради совместимости интерфейса и здесь не используется.
        """
        self._validate_settings()
        profile_url = self._build_profile_url(profile_username)
        known = known_external_ids or set()
        limit = settings.SAFETY_MAX_ITEMS

        print(f"Opening Instagram profile: {profile_username}")

        async with PlaywrightClient() as client:
            page = await client.new_page()
            try:
                await self._open_profile(page, profile_url)
                post_links = await self._collect_links_with_scroll(page, limit)
            finally:
                await page.close()

            new_links = [url for url in post_links if self._extract_external_id(url) not in known]
            print(f"Profile {profile_username}: {len(post_links)} posts in feed, {len(new_links)} new.")

            raw_posts: list[RawPostAddSchema] = []
            for post_url in new_links:
                try:
                    raw_post = await self._parse_post(client, profile_username, post_url)
                except Exception as e:  # один сломанный пост не должен валить весь парсинг
                    print(f"Failed to parse {post_url}: {e}")
                    continue

                if raw_post is None:
                    continue

                raw_posts.append(raw_post)
                await asyncio.sleep(random.uniform(2, 5))  # небольшая пауза, чтобы не ловить бан

            print(f"Parsed {len(raw_posts)} posts from profile {profile_username}.")
            return raw_posts

    # ------------------------------------------------------------------ #
    # Настройки и URL
    # ------------------------------------------------------------------ #
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
        return f"{INSTAGRAM_URL}/{normalized_username}/"

    # ------------------------------------------------------------------ #
    # Сессия и логин
    # ------------------------------------------------------------------ #
    async def _load_session(self, page: Page) -> None:
        """Подгружаем куки из сохранённого storage_state (context.storage_state() только СОХРАНЯЕТ)."""
        path = settings.INSTAGRAM_SESSION_STATE_PATH
        if not path or not Path(path).exists():
            return
        try:
            state = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Cannot read session file {path}: {e}")
            return
        cookies = state.get("cookies", [])
        if cookies:
            await page.context.add_cookies(cookies)
            print(f"Loaded {len(cookies)} cookies from {path}")

    async def _save_session(self, page: Page) -> None:
        path = settings.INSTAGRAM_SESSION_STATE_PATH
        if not path:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await page.context.storage_state(path=path)
        print(f"Session saved to {path}")

    async def _has_session_cookie(self, page: Page) -> bool:
        cookies = await page.context.cookies(INSTAGRAM_URL)
        return any(c["name"] == "sessionid" and c.get("value") for c in cookies)

    async def _is_logged_in(self, page: Page) -> bool:
        # Раньше тут проверялся селектор "nav", а он есть и на странице логина.
        if not await self._has_session_cookie(page):
            return False
        return await page.locator("input[name='password']").count() == 0

    async def _login(self, page: Page) -> None:
        if not settings.INSTAGRAM_USERNAME or not settings.INSTAGRAM_PASSWORD:
            raise RuntimeError("Нужны INSTAGRAM_USERNAME и INSTAGRAM_PASSWORD (или валидный файл сессии).")

        print("Trying to log into Instagram...")
        await page.goto(f"{INSTAGRAM_URL}/accounts/login/", wait_until="domcontentloaded")
        await self._dismiss_dialogs(page)

        username_input = page.locator("input[name='username'], input[name='email']").first
        password_input = page.locator("input[name='password'], input[name='pass']").first
        await username_input.wait_for(state="visible", timeout=15_000)
        await username_input.fill(settings.INSTAGRAM_USERNAME)
        await password_input.fill(settings.INSTAGRAM_PASSWORD)
        await page.locator("button[type='submit']").first.click()

        # Ждём появления cookie sessionid — это и есть признак успешного входа
        for _ in range(30):
            if await self._has_session_cookie(page):
                break
            if "challenge" in page.url or "two_factor" in page.url:
                raise RuntimeError(
                    "Instagram запросил подтверждение (checkpoint/2FA). "
                    "Войдите вручную один раз и сохраните storage_state."
                )
            await page.wait_for_timeout(1_000)
        else:
            raise RuntimeError("Не дождались входа в Instagram (неверный пароль, капча или изменилась форма).")

        await self._dismiss_dialogs(page)  # "Save login info?" -> "Not now"
        if settings.INSTAGRAM_SAVE_SESSION:
            await self._save_session(page)

    async def _open_profile(self, page: Page, profile_url: str) -> None:
        await self._load_session(page)
        # networkidle на Instagram практически не наступает (постоянные запросы), поэтому domcontentloaded
        await page.goto(profile_url, wait_until="domcontentloaded")
        await self._dismiss_dialogs(page)

        if settings.INSTAGRAM_LOGIN_REQUIRED and not await self._is_logged_in(page):
            await self._login(page)
            await page.goto(profile_url, wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)
            if not await self._is_logged_in(page):
                raise RuntimeError("Login failed: после входа Instagram всё равно просит авторизацию.")

        try:
            await page.wait_for_selector("a[href*='/p/'], a[href*='/reel/']", timeout=15_000)
        except PlaywrightError:
            print("No posts found on profile page (закрытый профиль, login wall или изменилась разметка).")

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
                    await button.wait_for(state="visible", timeout=1_000)
                    await button.click()
                    break
                except PlaywrightError:
                    continue

    # ------------------------------------------------------------------ #
    # Ссылки на посты
    # ------------------------------------------------------------------ #
    async def _collect_post_links(self, page: Page) -> list[str]:
        # В DOM href относительные (/username/p/XXXX/), поэтому startswith("https://...") ничего не находил
        hrefs = await page.eval_on_selector_all(
            "a[href*='/p/'], a[href*='/reel/']",
            "els => els.map(e => e.getAttribute('href'))",
        )
        links: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            if not href:
                continue
            url = urljoin(INSTAGRAM_URL, href).split("?")[0]
            external_id = self._extract_external_id(url)
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)
            links.append(url)
        return links

    async def _collect_links_with_scroll(self, page: Page, limit: int) -> list[str]:
        links = await self._collect_post_links(page)
        stagnant_rounds = 0
        max_scrolls = max(settings.INSTAGRAM_SCROLL_COUNT, 1) * 10

        for _ in range(max_scrolls):
            if len(links) >= limit or stagnant_rounds >= 3:
                break
            await page.mouse.wheel(0, 5_000)
            await page.wait_for_timeout(1_500)
            new_links = await self._collect_post_links(page)
            stagnant_rounds = stagnant_rounds + 1 if len(new_links) == len(links) else 0
            links = new_links

        return links[:limit]

    # ------------------------------------------------------------------ #
    # Парсинг одного поста
    # ------------------------------------------------------------------ #
    async def _parse_post(
        self, client: PlaywrightClient, profile_username: str, post_url: str
    ) -> RawPostAddSchema | None:
        external_id = self._extract_external_id(post_url)
        if not external_id:
            return None

        page = await client.new_page()
        captured: list[Response] = []

        def on_response(response: Response) -> None:
            if "graphql" in response.url or "/api/v1/" in response.url:
                captured.append(response)

        # ВАЖНО: слушатель вешаем ДО goto, иначе все ответы уже пройдут мимо
        page.on("response", on_response)

        try:
            await page.goto(post_url, wait_until="domcontentloaded")
            await self._dismiss_dialogs(page)
            try:
                await page.wait_for_selector("article, video", timeout=4_000)
            except PlaywrightError:
                pass  # без логина DOM часто пустой, данные всё равно лежат во встроенном JSON
            await page.wait_for_timeout(2_000)  # даём догрузиться XHR (было asyncio.sleep(3000) = 50 минут)

            payloads = await self._collect_payloads(page, captured)
            post_node = self._pick_post_node(payloads, external_id)

            media_urls = self._media_from_node(post_node) if post_node else []
            if not media_urls:
                print(f"API/JSON gave no media for {external_id}, falling back to DOM")
                media_urls = await self._extract_media_from_dom(page)

            caption = (self._caption_from_node(post_node) if post_node else None) or await self._extract_caption(page)
            published_at = (
                self._published_from_node(post_node) if post_node else None
            ) or await self._extract_published_at(page)
            thumbnail_url = await self._extract_thumbnail_url(page)
        finally:
            await page.close()

        # Пустой пост не сохраняем: иначе он попадёт в БД и больше никогда не перепарсится
        if not media_urls and not caption:
            print(f"Nothing extracted for {external_id}, will retry next cycle.")
            return None

        media_paths = await self._download_media_files(external_id, media_urls)
        thumbnail_path = await self._download_thumbnail(external_id, thumbnail_url)

        return RawPostAddSchema(
            source=PropertySource.INSTAGRAM.value,
            profile_username=profile_username,
            external_id=external_id,
            post_url=post_url,  # pydantic сам провалидирует как HttpUrl
            post_title=self._extract_post_title(caption),
            raw_caption=caption,
            media_urls=self._serialize_media_urls(media_urls),
            media_paths=self._serialize_media_urls(media_paths),
            thumbnail_url=thumbnail_url,
            thumbnail_path=thumbnail_path,
            published_at=published_at,
            ai_status="new",
        )

    # ------------------------------------------------------------------ #
    # Достаём данные поста из JSON (XHR-ответы + JSON, встроенный в HTML)
    # ------------------------------------------------------------------ #
    async def _collect_payloads(self, page: Page, responses: list[Response]) -> list[Any]:
        payloads: list[Any] = []

        # При прямом открытии /p/XXX/ данные часто лежат прямо в HTML, а не в XHR
        scripts = await page.eval_on_selector_all(
            "script[type='application/json']",
            "els => els.map(e => e.textContent)",
        )
        for text in scripts:
            if not text or ("image_versions2" not in text and "video_versions" not in text):
                continue
            try:
                payloads.append(json.loads(text))
            except json.JSONDecodeError:
                continue

        for response in responses:
            try:
                payloads.append(await response.json())
            except Exception:
                continue  # не JSON / тело уже недоступно

        return payloads

    def _find_post_nodes(self, data: Any, external_id: str) -> Iterator[dict]:
        """Ищем во вложенном JSON узел именно нашего поста (по shortcode), а не соседние посты."""
        if isinstance(data, dict):
            if data.get("code") == external_id and any(
                key in data for key in ("image_versions2", "video_versions", "carousel_media")
            ):
                yield data
            for value in data.values():
                yield from self._find_post_nodes(value, external_id)
        elif isinstance(data, list):
            for item in data:
                yield from self._find_post_nodes(item, external_id)

    def _pick_post_node(self, payloads: list[Any], external_id: str) -> dict | None:
        best_node: dict | None = None
        best_count = -1
        for payload in payloads:
            for node in self._find_post_nodes(payload, external_id):
                count = len(self._media_from_node(node))
                if count > best_count:
                    best_node, best_count = node, count
        return best_node

    def _media_from_node(self, node: dict) -> list[str]:
        items = node.get("carousel_media") or [node]
        urls: list[str] = []
        for item in items:
            url = self._best_media_url(item)
            if url and url not in urls:
                urls.append(url)
        return urls

    @staticmethod
    def _best_media_url(item: dict) -> str | None:
        videos = item.get("video_versions") or []
        if videos:
            return videos[0].get("url")
        candidates = (item.get("image_versions2") or {}).get("candidates") or []
        if candidates:
            return candidates[0].get("url")  # первый кандидат — самое большое разрешение
        return None

    @staticmethod
    def _caption_from_node(node: dict) -> str | None:
        caption = node.get("caption")
        text = caption.get("text") if isinstance(caption, dict) else caption
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None

    @staticmethod
    def _published_from_node(node: dict) -> datetime | None:
        taken_at = node.get("taken_at")
        if isinstance(taken_at, (int, float)):
            return datetime.fromtimestamp(taken_at, tz=timezone.utc)
        return None

    # ------------------------------------------------------------------ #
    # Запасной вариант: достаём из DOM
    # ------------------------------------------------------------------ #
    async def _extract_media_from_dom(self, page: Page) -> list[str]:
        urls: list[str] = []
        for _ in range(20):  # максимум слайдов в карусели
            current = await self._collect_current_slide_media(page)
            for url in current:
                if url not in urls:
                    urls.append(url)
            if not await self._go_to_next_slide(page, "|".join(current)):
                break
        print(f"Found {len(urls)} media URLs via DOM")
        return urls

    async def _collect_current_slide_media(self, page: Page) -> list[str]:
        article = page.locator("article").first
        urls: list[str] = []
        if await article.count() == 0:
            return urls

        images = article.locator("img")
        for index in range(await images.count()):
            image = images.nth(index)
            alt = (await image.get_attribute("alt") or "").lower()
            if "profile picture" in alt or "фото профиля" in alt:
                continue  # раньше этот continue стоял ПОСЛЕ добавления, поэтому аватарки попадали в список
            src = await image.get_attribute("src")
            if src and src.startswith("http") and src not in urls:
                urls.append(src)

        videos = article.locator("video")
        for index in range(await videos.count()):
            src = await videos.nth(index).get_attribute("src")
            # blob: скачать нельзя — реальные видео надёжнее брать из JSON (video_versions)
            if src and src.startswith("http") and src not in urls:
                urls.append(src)

        return urls

    async def _go_to_next_slide(self, page: Page, previous_snapshot: str | None) -> bool:
        candidates = [
            page.locator("button[aria-label='Next'], [role='button'][aria-label='Next']").first,
            page.get_by_role("button", name=re.compile("next|далее|следующее", re.IGNORECASE)).first,
        ]
        for button in candidates:
            try:
                await button.wait_for(state="visible", timeout=500)
                await button.click()
            except PlaywrightError:
                continue

            for _ in range(10):
                await page.wait_for_timeout(300)
                current = await self._collect_current_slide_media(page)
                snapshot = "|".join(current)
                if snapshot and snapshot != previous_snapshot:
                    return True
            return False
        return False

    # ------------------------------------------------------------------ #
    # Текстовые поля из DOM (запасной вариант)
    # ------------------------------------------------------------------ #
    async def _extract_caption(self, page: Page) -> str | None:
        selectors = [
            "article h1",
            "article ul li h1",
            "article ul li span",
        ]
        for selector in selectors:
            text = await self._get_text(page.locator(selector).first)
            if text and len(text) > 10:
                return text

        meta = page.locator("meta[property='og:description']")
        if await meta.count() > 0:
            content = await meta.first.get_attribute("content")
            if content and content.strip():
                return content.strip()
        return None

    def _extract_post_title(self, caption: str | None) -> str | None:
        if not caption:
            return None
        normalized_caption = caption.strip()
        return normalized_caption or None

    async def _extract_thumbnail_url(self, page: Page) -> str | None:
        meta = page.locator("meta[property='og:image']")
        if await meta.count() == 0:
            return None
        content = await meta.first.get_attribute("content")
        return content.strip() if content else None

    async def _extract_published_at(self, page: Page) -> datetime | None:
        time_element = page.locator("time[datetime]").first
        if await time_element.count() == 0:  # без этой проверки get_attribute ждёт 30 секунд
            return None
        value = await time_element.get_attribute("datetime")
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    async def _get_text(self, locator: Locator) -> str | None:
        try:
            if await locator.count() == 0:
                return None
            text = (await locator.inner_text()).strip()
            return text or None
        except PlaywrightError:
            return None

    # ------------------------------------------------------------------ #
    # Скачивание файлов
    # ------------------------------------------------------------------ #
    async def _download_media_files(self, external_id: str, media_urls: list[str]) -> list[str]:
        saved_paths: list[str] = []
        if not media_urls:
            print(f"No media URLs to download for {external_id}")
            return saved_paths

        print(f"Downloading {len(media_urls)} media files for {external_id}")
        target_dir = STORAGE_DIR / external_id
        target_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
            for index, media_url in enumerate(media_urls, start=1):
                file_path = target_dir / f"media_{index}{self._guess_extension(media_url, default='.jpg')}"
                try:
                    response = await http.get(media_url)
                    response.raise_for_status()
                    file_path.write_bytes(response.content)
                    saved_paths.append(str(file_path))
                except Exception as e:
                    print(f"Failed to download {media_url}: {e}")

        return saved_paths

    async def _download_thumbnail(self, external_id: str, thumbnail_url: str | None) -> str | None:
        if not thumbnail_url:
            return None

        target_dir = STORAGE_DIR / external_id
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"thumbnail{self._guess_extension(thumbnail_url, default='.jpg')}"

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
            try:
                response = await http.get(thumbnail_url)
                response.raise_for_status()
                file_path.write_bytes(response.content)
                return str(file_path)
            except Exception as e:
                print(f"Failed to download thumbnail {thumbnail_url}: {e}")
                return None

    def _guess_extension(self, url: str, default: str) -> str:
        path = urlparse(url).path
        suffix = Path(path).suffix.lower()
        if suffix:
            return suffix
        # Раньше из-за приоритета and/or условие срабатывало неправильно
        if "video" in path or "reel" in path:
            return ".mp4"
        return default

    def _serialize_media_urls(self, media_urls: list[str]) -> str | None:
        if not media_urls:
            return None
        return "\n".join(media_urls)

    def _extract_external_id(self, post_url: str) -> str | None:
        match = re.search(r"/(?:p|reel)/([^/?]+)", post_url)
        return match.group(1) if match else None
