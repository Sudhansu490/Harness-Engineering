from __future__ import annotations     # for type hints — lets us write `page: Page` without Python error, for clean typing

import os

from dotenv import load_dotenv

load_dotenv()

import asyncio
from agent.browser import harness_browser
from agent.executor import run_naive_agent

async def main() -> None:
    repo_url = os.environ.get(
        "TARGET_REPO_URL",
        "https://github.com/codebasics-community/nanoagents",
    )
    print(f"[naive] Target: {repo_url}")
    async with harness_browser(headless=False) as page:
        await run_naive_agent(page,repo_url)

# page = browser tab (like Chrome tab) — agent uses it to open and click the GitHub page

if __name__ == "__main__":
    asyncio.run(main())
