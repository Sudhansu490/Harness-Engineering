# 🛠️ Harness Engineering

**Harness Engineering** is a demonstration project built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Playwright](https://playwright.dev/).  
It illustrates the critical need for "Harness Engineering" — verifying an AI agent's actions against reality (e.g., actual DOM state) rather than trusting its self-reported claims.

---

## 🏗️ Architecture

- **Naive Agent** – A basic LangChain agent that attempts to perform actions on a browser page but blindly trusts its own output.
- **Harness Verifier** – A robust evaluation layer that reads the exact DOM state (e.g., verifying if a button is actually pressed) to establish ground truth.
- **Playwright Environment** – Provides a thread-safe, asynchronous browser environment for the agent to navigate and interact with web pages.

**Harnessed variant adds:**
- **IterationGuardMiddleware** – caps at `MAX_ITERATIONS=8` (`agent/middleware.py`)
- **LoginGuardMiddleware** – detects GitHub login wall and injects credentials (`GITHUB_USERNAME`/`GITHUB_PASSWORD`)
- **VerifyOnFinishMiddleware** + **ContextualPromptMiddleware** – re-checks DOM truth on `finish()` and feeds corrections

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12+ and `pip` installed (must match `pyproject.toml` `requires-python >=3.12`)

### Installation

```bash
# minimal — only Playwright + browser
pip install playwright
python -m playwright install chromium

# full project install (recommended — installs langchain, langgraph, langchain-groq, python-dotenv)
# pip install .
# python -m playwright install chromium
```

> **Note:** With only `playwright`, `python -m agent` will fail (`ModuleNotFoundError: langchain_groq`) because `agent/executor.py` and `agent/tools.py` need the other deps from `pyproject.toml`. Use the full install above if you want the agent to run.

Create your env file:
```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Required in `.env`:
```ini
GROQ_API_KEY=your_groq_api_key
GITHUB_USERNAME=your_github_username   # for login wall
GITHUB_PASSWORD=your_github_password
# Optional:
# GROQ_MODEL=openai/gpt-oss-20b   # default — configurable, used in agent/executor.py
# TARGET_REPO_URL=https://github.com/codebasics-community/nanoagents  # default in agent/__main__.py
```

### Running the Project

Run from the `harnessed-agent/` directory (where `pyproject.toml` lives — required so `agent` package imports resolve):

```bash
python -m agent
# equivalent explicit form:
# python -m agent.__main__
```

This executes `agent/__main__.py` (`harness_browser` + `run_naive_agent`). A visible Chromium window opens (`headless=False` in `agent/browser.py`).

Verify Playwright before running:
```bash
python -m playwright --help
```

### Expected Behavior

The **harnessed** agent handles the login wall and verifies DOM truth via middleware — unlike the naive agent which claims success blindly:

```text
[harnessed] Agent finished
  DOM reality   : starred=True, reason='star button shows 'Unstar''
  Iterations used: 3/8

[harnessed] SUCCESS: repo is genuinely starred.
```

If it cannot star within limits:

```text
[harnessed] Agent finished
  DOM reality   : starred=False, reason='star button still shows 'Star' -- action did not take effect'
  Iterations used: 8/8

[harnessed] FAILURE: max iterations reached without success.
```

*Contrast with naive (`naive-agent` branch) which prints `Model claimed: ...` vs `DOM reality: starred=False` and `FAILURE: the model got hit by login` — harness prevents that false-positive.*
