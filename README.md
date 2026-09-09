# Harness Engineering

**Harness Engineering** — verifying an AI agent's actions against reality (DOM) rather than trusting its claims. Built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Playwright](https://playwright.dev/).

---

## Branches — Pick Your View

This repo uses **branch-filtered projects** — choose a branch from the GitHub dropdown to see only that project:

| Branch | What you see | Path |
|--------|--------------|------|
| `main` (here) | **Overview only** — this README | `README.md` |
| `Naive` | **Naive Agent** — basic LangChain agent that blindly trusts its output (see `naive-agent/`) | `https://github.com/Sudhansu490/Harness-Engineering/tree/Naive` |
| `Harness` | **Harnessed Agent** — robust verifier that checks DOM ground truth (see `harnessed-agent/`) | `https://github.com/Sudhansu490/Harness-Engineering/tree/Harness` |

> **Viewer guide:** Top-left branch switcher `main` → select `Naive` to see naive project, `Harness` to see harnessed-agent. `main` intentionally shows only this overview.

---

## Quick Links

- **Naive branch** — `naive-agent/README.md` : `pip install playwright` + `python -m playwright install chromium` then `python -m agent` (or `python -m agent.__main__`)
- **Harness branch** — `harnessed-agent/README.md` : harness verifier + login/middleware flow

---

## Architecture Overview

- **Naive Agent** — attempts browser actions, trusts self-reported success.
- **Harness Verifier** — reads exact DOM state (e.g., `starred` button) to establish truth.
- **Playwright Environment** — async, thread-safe browser via `harness_browser` (`agent/browser.py`).

See branch-specific READMEs for setup, env (`GROQ_API_KEY`, `GROQ_MODEL`, `TARGET_REPO_URL`), and expected behavior.
