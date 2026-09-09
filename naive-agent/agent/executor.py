from __future__ import annotations

import os

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_groq import ChatGroq
from playwright.async_api import Page

from agent.context import HarnessContext
from agent.tools import TOOLS
from agent.verify import verify

SYSTEM_PROMPT = (
    "You are a browser agent. Your only job is to star a GitHub repository "
    "using the tools provided. When you believe the repo is starred, call "
    "finish()."
)


def _build_agent():
    api_key = os.environ.get("GROQ_API_KEY")
    model_name = os.environ.get("GROQ_MODEL", "llama3-70b-8192")

    model = ChatGroq(
        model_name=model_name,
        groq_api_key=api_key,
    )

    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        context_schema=HarnessContext,
    )


async def _execute_agent(page: Page, target_repo_url: str) -> str:
    agent = _build_agent()
    print("[naive] Starting agent (no harness) ...")
    try:
        await page.goto(target_repo_url, wait_until="domcontentloaded")
    except Exception as e:
        print(f"[naive] Navigation to {target_repo_url} failed: {e}")

    result = await agent.ainvoke(
        {"messages": [HumanMessage(f"Star this repo: {target_repo_url}")]},
        context=HarnessContext(page=page, repo_url=target_repo_url),
    )

    last_message = result["messages"][-1]
    return getattr(last_message, "content", str(last_message))


def _report_results(model_claim: str, ground_truth: dict) -> dict:
    print("\n" + "=" * 60)
    print("[naive] Agent finished")
    print(f"  Model claimed: {model_claim.strip()}")
    print(f"  DOM reality  : starred={ground_truth['passed']}, "
          f"reason='{ground_truth['reason']}'")
    print("=" * 60)

    return {
        "success": ground_truth["passed"],
        "model_claim": model_claim,
        **ground_truth,
    }


async def run_naive_agent(page: Page, target_repo_url: str) -> dict:
    """Run the naive (no-harness) LangChain agent and return a result dict."""
    model_claim = await _execute_agent(page, target_repo_url)
    ground_truth = await verify(page)
    return _report_results(model_claim, ground_truth)
