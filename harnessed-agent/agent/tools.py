from __future__ import annotations
from langchain.tools import ToolRuntime, tool
from agent.context import HarnessContext


@tool
async def navigate(url: str, runtime: ToolRuntime[HarnessContext]) -> str:
    """Navigate the browser to a URL.

    Only use this to go to the target GitHub repository page -- not for
    arbitrary browsing.

    Args:
        url: The full URL to navigate to.
    """
    page = runtime.context.page
    try:
        await page.goto(url, wait_until="domcontentloaded")
    except Exception as e:
        return f"Navigation failed: {str(e)}"
    return f"Navigated to {page.url}"


@tool
async def click_star_button(runtime: ToolRuntime[HarnessContext]) -> str:
    """Click the repository Star button. Use this when you want to star a repository.
    """
    from agent.verify import repo_is_starred

    page = runtime.context.page

    if await repo_is_starred(page):
        return "Repository is already starred."

    # Try multiple selectors — GitHub changes its DOM often.
    # Ordered from most specific to most generic.
    candidates = [
        'button[aria-label*="Star this repository"]',
        'button[data-testid="star-button"]',
        'button:has-text("Star")',
        'form[action*="/star"]:not([action*="/unstar"]) button[type="submit"]',
        '[aria-label*="Star this repository"]',
    ]

    button = None
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            if await loc.count() > 0 and await loc.is_visible():
                button = loc
                break
        except Exception:
            continue

    if button is None:
        # Fallback: any visible button containing "Star" but not "Starred"/"Unstar"
        fallback = page.locator('button:visible').filter(has_text="Star")
        try:
            count = await fallback.count()
            for i in range(min(count, 5)):
                try:
                    cand = fallback.nth(i)
                    text = (await cand.inner_text() or "").strip()
                    # Avoid "Starred" / "Unstar" — those mean already starred
                    if text == "Star" and await cand.is_visible():
                        button = cand
                        break
                except Exception:
                    continue
        except Exception:
            pass

    if button is None:
        # Debug help for next run — log what buttons exist
        try:
            all_btns = await page.locator('button:visible').all_inner_texts()
            preview = ", ".join([t.strip()[:20] for t in all_btns[:10] if t.strip()])
            return f"No 'Star' button found on the current page. Visible buttons: [{preview}] url={page.url}"
        except Exception:
            return f"No 'Star' button found on the current page. url={page.url}"

    try:
        await button.click(timeout=5000)
    except Exception as e:
        # Retry once with force click after short wait
        await page.wait_for_timeout(800)
        try:
            await button.click(force=True, timeout=5000)
        except Exception:
            return f"Failed to click Star button: {e}"

    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(800)
    # Verify after click
    if await repo_is_starred(page):
        return "Clicked the Star button — now starred."
    return "Clicked the Star button."



@tool
async def finish(summary: str, runtime: ToolRuntime[HarnessContext]) -> str:
    """Signal that the task is complete.
    """
    return f"finish() called: {summary}"


TOOLS = [navigate, click_star_button, finish]
