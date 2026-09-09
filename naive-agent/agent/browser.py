from __future__ import annotations

from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Page, Browser


@asynccontextmanager
async def harness_browser(headless: bool = False):
    """
    Yields a ready-to-use Playwright Page. Guarantees the browser is closed
    on the way out, even if the agent loop throws.
    """
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page: Page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()
            await browser.close()
