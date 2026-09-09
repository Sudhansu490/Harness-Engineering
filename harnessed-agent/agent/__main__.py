from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env next to harnessed-agent/, not CWD
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)

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


if __name__ == "__main__":
    asyncio.run(main())
