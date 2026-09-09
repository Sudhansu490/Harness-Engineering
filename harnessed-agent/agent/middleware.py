from __future__ import annotations

from collections.abc import Callable, Awaitable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
    hook_config,
)
from langchain.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from typing_extensions import NotRequired

from agent.context import HarnessContext

# ---------------------------------------------------------------------------
# 1. IterationGuardMiddleware
#    Pillar: guardrails cap -- hard stop so a confused model can't loop forever.
#    Context engineering: custom state schema tracks iteration_count across
#    every before_model call and jumps to "end" when the limit is hit.
# ---------------------------------------------------------------------------

class _IterGuardState(AgentState):
    """Agent state extended with an iteration counter."""
    iteration_count: NotRequired[int]


class IterationGuardMiddleware(AgentMiddleware[_IterGuardState]):
    """Hard cap on model calls. Model cannot talk past this limit."""

    state_schema = _IterGuardState

    def __init__(self, max_iterations: int = 8) -> None:
        super().__init__()
        self.max_iterations = max_iterations

    @hook_config(can_jump_to=["end"])
    def before_model(
        self, state: _IterGuardState, runtime: Runtime
    ) -> dict[str, Any] | None:
        count = state.get("iteration_count", 0) + 1
        print(f"  [IterationGuard] iteration {count}/{self.max_iterations}")
        if count >= self.max_iterations:
            print(f"  [IterationGuard] limit reached -- terminating agent")
            return {
                "iteration_count": count,
                "messages": [AIMessage(
                    f"Maximum iterations ({self.max_iterations}) reached. "
                    "Stopping without completing the task."
                )],
                "jump_to": "end",
            }
        return {"iteration_count": count}


# ---------------------------------------------------------------------------
# 2. LoginGuardMiddleware
#    Pillar: deterministic login handler.
#    The model NEVER sees or decides about credentials. Code runs before every
#    model call and handles login silently if GitHub has redirected.
# ---------------------------------------------------------------------------

class LoginGuardMiddleware(AgentMiddleware):
    """Deterministically logs in before each model call if needed.

    Credentials live only here in the harness -- never in the prompt and never
    in the model's tool results. The model sees a normal repo page, not a
    '/login' redirect. This is identical in intent to agent/login.py but
    expressed as LangChain life-cycle context.
    """

    async def abefore_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        ctx: HarnessContext = runtime.context
        page = ctx.page

        from agent.login import ensure_logged_in, is_logged_in, is_on_login_page

        if await is_on_login_page(page) or not await is_logged_in(page):
            print("  [LoginGuard] Not logged in -- authenticating ...")
            await ensure_logged_in(page)
            await page.goto(ctx.repo_url, wait_until="domcontentloaded")
            print("  [LoginGuard] Authenticated; back on repo page.")
        else:
            print("  [LoginGuard] Already logged in -- skipping.")

        return None  # No state update needed


# ---------------------------------------------------------------------------
# 3. ContextualPromptMiddleware
#    Pillar / Context Engineering: dynamic model context.
#    Before each model call, reads the live page state and appends it to the
#    system message (transient -- does NOT write to state). The model always
#    has current ground truth about url / logged_in / starred / star_count
#    without having to call read_page_state first.
# ---------------------------------------------------------------------------

class ContextualPromptMiddleware(AgentMiddleware):
    """Injects live page state into the system prompt before every model call.

    This is a transient update -- modifies what the model sees for this single
    call without persisting anything to state. Uses wrap_model_call and
    request.override(system_message=...) per the LangChain middleware docs.
    """

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        ctx: HarnessContext = request.runtime.context  # type: ignore[union-attr]
        page = ctx.page

        from agent.login import is_logged_in
        from agent.verify import read_star_count, repo_is_starred

        logged_in_status = await is_logged_in(page)
        starred_status = await repo_is_starred(page)
        star_count_status = await read_star_count(page)

        snapshot = (
            f"url={page.url} "
            f"logged_in={logged_in_status} "
            f"starred={starred_status} "
            f"star_count={star_count_status}"
        )
        print(f"  [ContextualPrompt] Page snapshot injected: {snapshot}")

        # Append snapshot as an extra text block to the existing system message.
        # content_blocks gives us a list regardless of whether original content
        # was a string or list (per LangChain middleware docs).
        existing_blocks = list(request.system_message.content_blocks)
        new_system = SystemMessage(
            content=existing_blocks + [
                {"type": "text", "text": f"\n\nCurrent browser state: {snapshot}"}
            ]
        )
        return await handler(request.override(system_message=new_system))


# ---------------------------------------------------------------------------
# 4. VerifyOnFinishMiddleware
#    Pillar: independent verifier.
#    Wraps every tool call. When the model calls finish(), the harness reads
#    the actual DOM via agent/verify.py BEFORE letting the tool return.
#    If verification fails, we short-circuit -- the tool never "completes" --
#    and feed the ground-truth failure back so the model tries again.
#    The model's word is NEVER the source of truth.
# ---------------------------------------------------------------------------

class VerifyOnFinishMiddleware(AgentMiddleware):
    """Intercepts finish() and independently verifies the DOM before trusting it.

    wrap_tool_call receives a ToolCallRequest (tool name is in
    request.tool_call['name'], runtime context in request.runtime.context).
    When finish() verification fails, we return a ToolMessage short-circuiting
    the actual tool and feeding the ground-truth failure reason back to the model.
    The model's claim is NEVER the source of truth.
    """

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        tool_name: str = request.tool_call["name"]

        if tool_name != "finish":
            # Not finish() -- pass through to actual tool execution
            result = await handler(request)
            print(f"  [tool] {tool_name} -> {str(result)[:120]}")
            return result

        # finish() was called -- run the independent DOM check FIRST
        ctx: HarnessContext = request.runtime.context
        page = ctx.page

        from agent.verify import verify
        report = await verify(page)

        print(
            f"  [VerifyOnFinish] Model called finish() -- DOM check: "
            f"passed={report['passed']}, reason='{report['reason']}'"
        )

        if report["passed"]:
            # Ground truth confirms success -- let finish() actually execute
            result = await handler(request)
            print("  [VerifyOnFinish] Verified. Task genuinely complete.")
            return result
        else:
            # Model was wrong. Short-circuit finish() entirely.
            # Return a ToolMessage so LangGraph treats it as a valid tool response;
            # the failure reason is fed back into the conversation and the model retries.
            print("  [VerifyOnFinish] Verification failed -- rejecting finish().")
            tool_call_id: str = request.tool_call["id"]
            return ToolMessage(
                content=(
                    f"Verification failed: {report['reason']}. "
                    "The repo is NOT starred yet. "
                    "Do NOT call finish() again until the page context confirms starred=True."
                ),
                tool_call_id=tool_call_id,
            )
