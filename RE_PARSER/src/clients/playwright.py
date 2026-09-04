from typing import Self

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from src.core.config import settings


class PlaywrightClient:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> Self:
        self._playwright = await async_playwright().start()
        browser_launcher = getattr(self._playwright, settings.BROWSER)
        browser = await browser_launcher.launch(headless=settings.HEADLESS)
        self._browser = browser
        self._context = await browser.new_context()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        if self._context is None:
            raise RuntimeError("Playwright context is not initialized.")

        page = await self._context.new_page()
        page.set_default_timeout(settings.TIMEOUT_MS)
        return page
