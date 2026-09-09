from __future__ import annotations

from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Page, Browser

# asynccontextmanager = for `async with` — makes `harness_browser()` give a page and auto-close browser even if agent crashes
# playwright.async_api = for browser+tab — gives `async_playwright`(engine), `Page`(tab), `Browser`(chrome instance) for automation


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
