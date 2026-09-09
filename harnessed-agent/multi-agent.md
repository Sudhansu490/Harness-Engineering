# Multi-Agent Architecture — Harness Engineering

> This project uses one browser agent today (`agent/executor.py:30`). This doc shows how to split it into several small agents that work together. The main rule stays: **never trust what the model says — only trust the real page (DOM) check**.

## Contents
0. End-to-End Trace — Where it Starts → Calls → Tools → Params → Output Flow
1. Specialization / Role-Based Agents
2. Orchestration / Coordination Patterns
3. Shared State & Memory
4. Communication Mechanisms
5. Control Flow Features
6. Other Important Production Features
7. How Each Agent Works
8. Agent Flows
9. Orchestration

---

## 0. End-to-End Trace — Where it Starts → What Calls What → How Output Flows

**One view of everything you asked:**

| Step | Starts Where | Function Called | Tool Used | Parameter Checked | Output | Goes To Next |
|------|--------------|-----------------|-----------|-------------------|--------|--------------|
| 0 | `agent/__main__.py:13` `main()` | `harness_browser()` (`agent/browser.py:8`) | — | `TARGET_REPO_URL` | `Page` opened | Executor |
| 1 | `agent/executor.py:54` `_execute_agent()` | `_build_agent()` (`agent/executor.py:30`) | — | `GROQ_API_KEY`, `MAX_ITERATIONS=5` | Agent ready | Navigator |
| 2 | Navigator | `navigate(url)` (`agent/tools.py:7`) | `navigate` | `page.url`, `domcontentloaded` | `ToolMessage("Navigated to ...")` | Auth check |
| 3 | Auth | `ensure_logged_in()` (`agent/login.py:68`) + `is_logged_in()` (`agent/login.py:50`) | — (code) | `is_on_login_page` (`agent/login.py:46`), `logged_in` | `auth_verified=True` or HITL wait (`agent/login.py:15`) | Interaction |
| 4 | Interaction | `click_star_button()` (`agent/tools.py:25`) | `click_star_button` | `starred` (`agent/verify.py:6`), `star_count` | `ToolMessage("Clicked Star")` | Verifier |
| 5 | Verifier | `verify()` (`agent/verify.py:35`) → `repo_is_starred()` (`agent/verify.py:6`) + `read_star_count()` (`agent/verify.py:28`) | — (read only) | 4 selectors: `Starred`/`Unstar`/`aria-pressed` | `{passed, reason, star_count}` → `last_verdict` | Supervisor |
| 6 | Supervisor | `finish(summary)` (`agent/tools.py:55`) via `VerifyOnFinish` (`agent/middleware.py:158`) | `finish` | `passed==true` + `iteration_count < 5` (`agent/middleware.py:33`) | `ToolMessage` success or `Verification failed → retry` | END or loop to 4 |

**Structure — Full call & output flow:**

```
 START  agent/__main__.py:13 main()
   │
   ▼
 harness_browser (agent/browser.py:8) ──► Page + repo_url (HarnessContext agent/context.py:5)
   │
   ▼
 _execute_agent (agent/executor.py:54) ──► _build_agent (executor.py:30) ──► agent.ainvoke (executor.py:62)
   │                                          │ IterationGuard(max=5) + LoginGuard + ContextualPrompt + VerifyOnFinish
   ▼                                          ▼
 Navigator ──navigate(url) (tools.py:7) ──► ToolMessage ──► Shared State (repo_url, page.url)
   │ check: page.url, /login?                              │
   ▼                                                        ▼
 Auth ──is_on_login_page (login.py:46) ──► is_logged_in (login.py:50) ──► ensure_logged_in (login.py:68)
   │ check: logged_in?  No ──► fill #login_field/#password ──► 2FA wait (login.py:15) ──► goto repo
   │ Yes ──► skip
   ▼
 Interaction ──ContextualPrompt snapshot (middleware.py:105/128) logged_in/starred
   │ check: starred?  Yes ──► "already starred" ──► skip click
   │ No ──► click_star_button (tools.py:25) ──► wait 500ms (tools.py:50) ──► ToolMessage
   ▼
 Verifier ──repo_is_starred (verify.py:6) + read_star_count (verify.py:28)
   │ check: Starred/Unstar/aria-pressed selectors          Output: {passed, reason, star_count}
   ▼                                                        │
 Shared State: last_verdict = {passed, reason} ────────────┘ writes, others read
   │
   ▼
 Supervisor ──read iteration_count + last_verdict ──► decide
   │ check: passed && count<5 ──► finish() (tools.py:55) ──► VerifyOnFinish (middleware.py:158) ──► DOM re-check
   │   passed? Yes ──► ToolMessage success ──► END ──► _report_results (executor.py:71) prints 3/5 + SUCCESS
   │   No  ──► ToolMessage "Verification failed" (middleware.py:204) ──► feeds back ──► loop to Interaction
   │ check: count>=5 ──► jump_to="end" (middleware.py:43) ──► END FAILURE
```

**Structure — How output passes between steps (the data, not just control):**

```
 navigate(url)        ──Output: ToolMessage("Navigated...") ──► messages[] ──► seen by Auth & Supervisor
 ensure_logged_in()   ──Output: auth_verified=True ──────────► state[auth_verified] ──► Supervisor skips Auth next loop
 click_star_button()  ──Output: ToolMessage("Clicked...") ──► messages[] + page DOM changed ──► Verifier reads DOM
 verify()             ──Output: {passed, reason, star_count} ──► state[last_verdict] + messages ──► Supervisor reads
 finish()             ──Output: if passed → ToolMessage("finish() called...") → END
                               if not passed → ToolMessage("Verification failed...") → back to Interaction (retry)
 All steps share: HarnessContext(page, repo_url) + state(iteration_count, starred, last_verdict) + thread_id (executor.py:65)
```

---

## 1. Specialization / Role-Based Agents

**In simple words:** Instead of one agent doing everything, give each agent one clear job.

| Role | Does What | Tools It Can Use |
|------|-----------|------------------|
| **Navigator** | Goes to the GitHub repo page | `navigate` (`agent/tools.py:7`) |
| **Auth** | Logs in if GitHub shows login page | No tool — runs code directly (`agent/login.py:68`, `agent/middleware.py:68`) |
| **Interaction** | Clicks the Star button | `click_star_button` (`agent/tools.py:25`) |
| **Verifier** | Checks if repo is really starred | Reads page only (`agent/verify.py:35`) |
| **Supervisor** | Decides who works next, handles retry and finish | `finish` (`agent/tools.py:55`) + handoff tools |

**Structure — Who reports to whom:**

```
              ┌──────────────┐
              │  Supervisor  │  boss, picks next agent
              └──────┬───────┘
      ┌──────────┬────┴────┬──────────┐
      ▼          ▼         ▼          ▼
 Navigator    Auth   Interaction  Verifier
  goes to    logs in   clicks    checks
  repo       if needed  Star     real page
```

**Why split?**
- Each agent can only do its own job (safer, easier to test).
- Passwords stay only with Auth — other agents never see them.
- Easy to test one agent with a fake page.

---

## 2. Orchestration / Coordination Patterns

**In simple words:** How agents work together and who decides what happens next.

| Pattern | Use When | In This Project |
|---------|----------|-----------------|
| **Supervisor (main choice)** | One goal, few agents, need retry logic | Supervisor picks: Navigator -> Auth -> Interaction -> Verifier -> finish |
| **Sequential Pipeline** | Steps always in same order | Page -> Navigator -> Auth -> Click -> Verify (no thinking needed) |
| **Parallel Fan-Out** | Same task for many repos | Supervisor runs same pipeline for many URLs at once |

**We recommend: Supervisor + Sequential together**

```
[Supervisor] -> Navigator -> Auth -> Interaction -> Verifier
      ^                                            |
      |________ retry if not starred (max 5) ______|
                       |
                    finish()
```

This keeps the current limit `MAX_ITERATIONS=5` (`agent/executor.py:28`) but the Supervisor is smart enough to choose *which* agent to retry.

---

## 3. Shared State & Memory

**In simple words:** Where agents store and read shared information.

| Layer | What It Holds | Today | In Multi-Agent |
|-------|---------------|-------|----------------|
| **Context (temporary)** | Page + repo URL for one turn | `HarnessContext` (`agent/context.py:5`) | Same, plus `last_verdict` |
| **Graph State (short-term)** | Counter, messages, starred? | `_IterGuardState` (`agent/middleware.py:28`) | One shared state: `iteration_count`, `starred`, `last_verdict` |
| **Checkpointer (long-term)** | Saves progress across restarts | `InMemorySaver` (`agent/executor.py:44`) | `AsyncPostgresSaver` for production |

**Structure — How memory is shared:**

```
  ┌─────────────────────────────────────────────┐
  │  Context (one turn)                         │  HarnessContext (agent/context.py:5)
  │  page + repo_url + last_verdict             │  lives only for current step
  └──────────────────────┬──────────────────────┘
                         ▼
  ┌─────────────────────────────────────────────┐
  │  Graph State (one run)                      │  _IterGuardState (agent/middleware.py:28)
  │  iteration_count, starred, messages         │  shared by all agents
  └──────────────────────┬──────────────────────┘
                         ▼
  ┌─────────────────────────────────────────────┐
  │  Checkpointer (many runs)                   │  InMemorySaver -> Postgres (agent/executor.py:44)
  │  saves full history by thread_id            │  survives restarts
  └─────────────────────────────────────────────┘
         All agents read/write the middle layer
```

**Simple rules:**
- Only Verifier writes the result. Others just read it.
- Live page info (`logged_in`, `starred`) is added to the prompt each turn but not saved forever (`agent/middleware.py:105`).
- All agents share the same `thread_id` so the full history can be replayed.

---

## 4. Communication Mechanisms

**In simple words:** How agents talk to each other.

| How | Example |
|-----|---------|
| **Handoff (`Command`)** | `Command(goto="verifier")` moves work to the next agent (`agent/middleware.py:16`) |
| **Shared State** | Navigator writes `repo_url`, Verifier reads it |
| **Message Passing** | All agents add messages to one shared list (`ToolMessage`, `AIMessage`) |
| **Direct Harness Help** | Before any agent runs, Auth checks login without asking the model (`agent/middleware.py:77`) |

**Structure — How they talk:**

```
  Navigator ──write repo_url──► Shared State ──read──► Verifier
      │                              ▲                   │
      └─── ToolMessage ──► messages ─┘                   │
                                                         │
  Interaction ── click result ──► Supervisor ◄── verify result ─┘
      │                              │
      │         ┌────────────────────┘
      │         ▼
      │   Command(goto="verifier")  (agent/middleware.py:16)
      │   Direct harness help: Auth checks login before any LLM step (agent/middleware.py:77)
```

**Keep it simple:**
- Pass small results (e.g. `{"passed": true, "reason": "..."}`), not the whole page HTML.
- Never pass passwords in messages — they stay inside Auth only.

---

## 5. Control Flow Features

**In simple words:** Rules that control loops, retries, and stopping.

| Feature | What Happens |
|---------|--------------|
| **Max Iterations** | Stop after 5 tries (`agent/middleware.py:33` -> `jump_to="end"`) |
| **Retry** | If click fails, wait 500ms (`agent/tools.py:50`) and try again |
| **Branch on Login** | If not logged in, go to Auth first (`agent/middleware.py:85`) |
| **Verify Before Finish** | `finish()` only works if page really shows Starred (`agent/middleware.py:158`) |

**Flow in 5 steps:**
```
START -> Check Login -> Navigator -> Click Star -> Verifier
                          |              |            |
                          |              |      passed? --No--> Retry (Supervisor)
                          |              |            |
                          |              |           Yes -> finish() -> END
```

Other useful controls: human help for 2FA (`agent/login.py:15`, waits 5 min), safe retry (already starred -> do nothing `agent/tools.py:32`), and timeouts per agent.

---

## 6. Other Important Production Features

**Structure — What production needs:**

```
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ Observability│  │   Security   │  │ Reliability  │
  │ logs + trace │  │ per-agent    │  │ safe browser │
  │ metric 3/5   │  │ tools, no    │  │ close, retry │
  │ (agent/mw:47)│  │ pwd leak     │  │ rate-limit   │
  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
         └─────────────────┼─────────────────┘
                           ▼
                  ┌────────────────┐
                  │ Harness Check  │  verify() must pass (agent/verify.py:35)
                  │ Cost: cheap    │  Navigator cheap, Supervisor strong
                  │ model tiering  │
                  └────────────────┘
```

- **Logging & Tracing:** Replace `print()` (`agent/middleware.py:47`) with structured logs + LangSmith tracing. Keep counter `Iterations used: 3/5` (`agent/executor.py:77`) as a metric.
- **Browser Safety:** Share one `Page` via `HarnessContext` (`agent/browser.py:8`), close it safely with `try/finally`. For parallel work, use separate browser contexts.
- **Security:** Each agent has its own tool list (`agent/tools.py:62` is split). Passwords stay in Auth. Page snapshot is added as system message, not user message.
- **Reliability:** Check `page.is_closed()` before each turn, rate-limit GitHub stars, fail fast if `GROQ_API_KEY` is missing.
- **Harness Check:** Every `finish()` must pass `verify()` (`agent/verify.py:35`). If selectors break (GitHub redesign), alert and fallback to manual review.
- **Cost & Speed:** Use cheap model for Navigator, strong model only for Supervisor/Interaction. Cache login check for 30s.

---

## 7. How Each Agent Works

**Structure — What each does step by step:**

```
 Navigator:  repo_url ──► navigate(url) (agent/tools.py:7) ──► check page.url ──► if /login ──► Auth
 Auth:       check is_on_login_page (agent/login.py:46) + is_logged_in (agent/login.py:50) ──► fill login ──► 2FA wait (agent/login.py:15) ──► goto repo
 Interaction: see snapshot starred=False (agent/middleware.py:128) ──► click_star_button (agent/tools.py:25) ──► if already starred: stop
 Verifier:   repo_is_starred (agent/verify.py:6) + read_star_count (agent/verify.py:28) ──► return {passed, reason, count} ──► only truth
 Supervisor: read last_verdict + count ──► pick next agent ──► or finish() ──► if verify fails (agent/middleware.py:198) ──► retry
```

- **Navigator:** Gets `repo_url` from Supervisor, calls `navigate(url)` (`agent/tools.py:7`), checks `page.url`. If sent to `/login`, hands off to Auth.
- **Auth (no LLM):** Checks `is_on_login_page` (`agent/login.py:46`) and `is_logged_in` (`agent/login.py:50`). If needed, fills `#login_field` / `#password`, handles device verification (`agent/login.py:15`), then goes back to repo page.
- **Interaction:** Sees snapshot `logged_in=True starred=False` (`agent/middleware.py:128`), calls `click_star_button` (`agent/tools.py:25`). If already starred, returns early — safe to retry.
- **Verifier:** Calls `repo_is_starred` (`agent/verify.py:6`) with 4 selectors and `read_star_count` (`agent/verify.py:28`). Returns `{"passed", "reason", "star_count"}`. This is the only truth.
- **Supervisor:** Reads `last_verdict` + `iteration_count`, picks next agent or calls `finish()`. If `finish()` fails verification (`agent/middleware.py:198`), it gets a message like `"Verification failed..."` and retries.

---

## 8. Agent Flows

### Happy Path — Success in 3 steps
```
START -> Navigator: navigate(repo) -> Auth: already logged in (skip)
      -> Interaction: click_star_button() -> Verifier: {"passed": true, reason: "shows Unstar"}
      -> Supervisor: finish() -> Verifier checks again -> END (SUCCESS 3/5)
```

### Login Wall — Recovery
```
START -> Navigator: sent to /login
      -> Auth: ensure_logged_in() -> fill login, wait for 2FA if needed, goto repo
      -> Interaction: click -> Verifier: passed -> finish() -> SUCCESS
```

### Verification Rejection — Retry
```
Interaction: click (page didn't update)
Supervisor: finish() -> VerifyOnFinish blocks it, returns "Verification failed: still shows Star" (`agent/middleware.py:204`)
Supervisor reads error + fresh snapshot starred=False -> Interaction retries -> Verifier passed -> finish() allowed -> SUCCESS
```

> If 5 tries fail, `IterationGuard` stops the run (`agent/middleware.py:43`): `iterations 5/5 -> FAILURE`.

---

## 9. Orchestration

**Who is the boss?** The Supervisor graph. Agents are workers and don't know the full plan.

**What the boss does:** Breaks task into steps, picks next agent (`Command`), saves shared state, handles errors (`LoginError` `agent/login.py:8`), enforces `MAX_ITERATIONS=5` (`agent/executor.py:28`) and the final `verify()` check.

**Structure — How the graph connects:**

```
             ┌─────────────┐
             │    START    │
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │  Navigator  │  go to repo page
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │    Auth     │  login if needed
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │ Interaction │  click Star
             └──────┬──────┘
                    ▼
             ┌─────────────┐
             │  Verifier   │  check real page
             └──────┬──────┘
                    │
            ┌───────┴────────┐
     passed │                │ not passed
            ▼                ▼
        ┌──────┐      ┌─────────────┐
        │ END  │      │ Interaction │ ── retry (loop)
        └──────┘      └─────────────┘
  Supervisor decides the next step. All share one Page (agent/browser.py:8)
  and one State (agent/context.py:5). Final check is always verify() (agent/verify.py:35).
```

**Run flow — From start to finish:**

```
 User asks: "Star this repo"
         │
         ▼
 harness_browser opens Page ──► Supervisor creates graph + shared state
         │                              │
         ▼                              ▼
   Page + repo_url ──────────► Navigator -> Auth -> Interaction -> Verifier
   (HarnessContext)                     │                    │
                                        │◄─── retry ────────┘
                                        ▼
                                   Supervisor calls finish()
                                        │
                                        ▼
                                   Verifier checks DOM
                                   passed? ──Yes──► END SUCCESS
                                      │
                                      No ──► tell Supervisor to retry
```

**Production checklist:**
- [ ] Use `AsyncPostgresSaver` (not memory) for restarts
- [ ] Store secrets in vault, only Auth can read them
- [ ] Enable `LANGSMITH_TRACING=true`
- [ ] CI must fail if `verify()["passed"] == False`

---

| File | Before (single agent) | After (multi-agent) |
|------|----------------------|---------------------|
| `agent/executor.py:30` | One agent | Supervisor graph + sub-agents |
| `agent/middleware.py:33,68,105,158` | 4 middleware | Per-agent + global guard |
| `agent/tools.py:62` | One tool list | Split per agent |
| `agent/verify.py:35` | After-run check | Verifier agent (always) |
| `agent/browser.py:8` | One Page | Shared Page via `HarnessContext` |

*Rule kept: the model's word is never the truth — only `verify(page)` is.*
