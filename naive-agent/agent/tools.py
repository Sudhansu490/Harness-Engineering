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

    page = runtime.context.page
    button = page.locator(
        'button[aria-label*="Star this repository"],'
        'form[action*="/star"]:not([action*="/unstar"]) button[type="submit"]'
    ).first

    if await button.count() == 0:
        return "No 'Star' button found on the current page."

    try:
        await button.click(force=True)
    except Exception:
        await page.wait_for_timeout(500)
        raise

    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(500)
    return "Clicked the Star button."



@tool
async def finish(summary: str, runtime: ToolRuntime[HarnessContext]) -> str:
    """Signal that the task is complete.
    """
    return f"finish() called: {summary}"


TOOLS = [navigate, click_star_button, finish]
