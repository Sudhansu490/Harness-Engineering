from __future__ import annotations

from playwright.async_api import Page


async def repo_is_starred(page: Page) -> bool:
    """
    Returns True if the repo is starred by the current user.

    GitHub shows different button states depending on context:
    - "Starred"  — the button label while you're on the repo page (visual toggle).
    - "Unstar"   — shown on hover / in the list dropdown.
    We must check both; relying only on "Unstar" causes starred=False
    immediately after a successful star click.
    """
    if await page.locator('button:has-text("Starred"):visible').count() > 0:
        return True

    if await page.locator('button:has-text("Unstar"):visible').count() > 0:
        return True

    if await page.locator('[aria-label*="Starred"]:visible').count() > 0:
        return True

    return await page.locator('[data-testid="star-button"][aria-pressed="true"]:visible').count() > 0


async def read_star_count(page: Page) -> str | None:
    counter = page.locator("#repo-stars-counter-star")
    if await counter.count() == 0:
        return None
    return await counter.first.get_attribute("title") or await counter.first.inner_text()


async def verify(page: Page) -> dict:
    """
    Ground truth check the loop calls after the model claims it's done.
    Returns a small report the harness can log or feed back to the model
    if it needs to retry.
    """
    starred = await repo_is_starred(page)
    return {
        "passed": starred,
        "star_count": await read_star_count(page),
        "reason": "star button shows 'Unstar'" if starred
        else "star button still shows 'Star' -- action did not take effect",
    }
