# 🛠️ Harness Engineering

**Harness Engineering** is a demonstration project built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Playwright](https://playwright.dev/).  
It illustrates the critical need for "Harness Engineering" — verifying an AI agent's actions against reality (e.g., actual DOM state) rather than trusting its self-reported claims.

---

## 🏗️ Architecture

- **Naive Agent** – A basic LangChain agent that attempts to perform actions on a browser page but blindly trusts its own output.
- **Harness Verifier** – A robust evaluation layer that reads the exact DOM state (e.g., verifying if a button is actually pressed) to establish ground truth.
- **Playwright Environment** – Provides a thread-safe, asynchronous browser environment for the agent to navigate and interact with web pages.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12+ and `pip` installed (must match `pyproject.toml` `requires-python >=3.12`)

### Installation

```bash
# minimal — only Playwright + browser (as you requested)
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
# Optional:
# GROQ_MODEL=openai/gpt-oss-20b   # default — configurable, used in agent/executor.py
# TARGET_REPO_URL=https://github.com/codebasics-community/nanoagents  # default in agent/__main__.py
```

### Running the Project

Run from the `naive-agent/` directory (where `pyproject.toml` lives — required so `agent` package imports resolve):

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
The naive agent will attempt to star a repository but might fail to interact correctly (e.g. hitting a login wall). It will likely claim success, but the harness verifier will catch the discrepancy:

```text
[naive] Agent finished
  Model claimed: I have successfully clicked the 'Star' button!
  DOM reality  : starred=False, reason='star button still shows 'Star' -- action did not take effect'

[naive] FAILURE: the model got hit by login and panicked.
        The harness trusted it. The DOM says otherwise.
        This is exactly what harness engineering prevents.
```