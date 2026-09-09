from __future__ import annotations

import asyncio
import os
from playwright.async_api import Page


class LoginError(Exception):
    pass


_VERIFICATION_TIMEOUT_S = 300  # 5 minutes


async def _wait_for_device_verification(page: Page) -> None:
    """HITL pause: wait for the human to enter the email verification code.

    GitHub's /sessions/verified-device page cannot be solved by the agent.
    We print a clear banner and poll until the browser navigates away,
    which happens automatically after the user enters the correct code.
    """
    print()
    print("=" * 60)
    print("  [LoginGuard] ⚠  HUMAN INPUT REQUIRED")
    print()
    print("  GitHub sent a verification code to your email.")
    print("  → Look at the open browser window.")
    print("  → Enter the code on the GitHub page.")
    print("  The agent will resume automatically once you submit.")
    print(f"  (Waiting up to {_VERIFICATION_TIMEOUT_S // 60} minutes ...)")
    print("=" * 60)
    print()

    deadline = asyncio.get_event_loop().time() + _VERIFICATION_TIMEOUT_S
    while "sessions/verified-device" in page.url:
        if asyncio.get_event_loop().time() > deadline:
            raise LoginError(
                "Timed out waiting for device verification. "
                f"No code was entered within {_VERIFICATION_TIMEOUT_S // 60} minutes."
            )
        await asyncio.sleep(1)

    print("  [LoginGuard] ✓ Device verification complete -- resuming agent.")


async def is_on_login_page(page: Page) -> bool:
    return "/login" in page.url


async def is_logged_in(page: Page) -> bool:
    """Checks for the avatar/nav menu that only renders when authenticated.

    GitHub has changed the aria-label on the user menu button across UI
    versions. We check all known variants so a future redesign doesn't
    silently break the login guard.
    """
    selectors = [
        '[aria-label="Open user navigation menu"]',  # GitHub UI 2023+
        '[aria-label="Open user account menu"]',     # GitHub UI pre-2023
        'meta[name="user-login"][content]:not([content=""])',  # reliable DOM signal
    ]
    for sel in selectors:
        if await page.locator(sel).count() > 0:
            return True
    return False


async def ensure_logged_in(page: Page) -> None:
    username = os.environ.get("GITHUB_USERNAME")
    password = os.environ.get("GITHUB_PASSWORD")

    if not username or not password:
        raise LoginError(
            "GITHUB_USERNAME / GITHUB_PASSWORD are not set. "
            "Copy .env.example to .env and fill them in."
        )

    if not await is_on_login_page(page):
        await page.goto("https://github.com/login")

    await page.fill("#login_field", username)
    await page.fill("#password", password)
    await page.click('input[type="submit"]')

    # GitHub may throw a "verify it's you" / 2FA screen. The harness can't
    # solve that autonomously -- fail loudly and clearly rather than let
    # the model hallucinate a workaround.
    await page.wait_for_load_state("domcontentloaded")

    if "sessions/verified-device" in page.url:
        await _wait_for_device_verification(page)
        return

    if await is_on_login_page(page) or "sessions/two-factor" in page.url:
        raise LoginError(
            "Login did not complete automatically -- GitHub likely "
            "presented a 2FA or verification challenge. Use an account "
            "with 2FA disabled for this demo, or log in manually once "
            "in a persistent browser profile."
        )
