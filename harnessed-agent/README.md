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
- Make sure you have `uv` installed. Follow the instructions [here](https://docs.astral.sh/uv/getting-started/installation/) to install it.
- Ensure that you have a Groq API key set up in your `.env` file (`GROQ_API_KEY`).
- We use the `llama3-70b-8192` model by default (configurable via `GROQ_MODEL`).

### Running the Project

Install playwright
```
playwright install
```
Setup UV environment
```
uv sync
```
To run the naive agent demonstration, execute the following command:
```bash
uv run -m agent
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

### Now run with Harness

The code for harness is present i harnessed git branch. Check out that branch by running this command

```
git checkout harnessed
```

Now run the agent again
```
uv run -m agent
```

This time it will successfully login and star the repo