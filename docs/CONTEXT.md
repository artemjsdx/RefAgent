# RefAgent — Session Context

> **NEW SESSION? Read this file first, then read docs/ARCHITECTURE.md**
>
> **WHO UPDATES THIS FILE:** The Replit coding agent updates this file
> at the end of every development session before pushing to GitHub.
> The RefAgent itself does NOT update this file.

---

## Current State

**Last updated:** 2026-06-11
**Session:** #1 (planning & design)
**Stage:** Pre-implementation — all design decisions made, ready to build

### What exists right now
- `plan.txt` — master plan with all 8 blocks
- `docs/ARCHITECTURE.md` — deep architecture decisions
- `docs/KNOWLEDGE_BASE.md` — all Telegram gotchas from real testing
- `docs/HANDOFF_PROMPT.md` — prompt to paste in new Replit session
- `README.md` — full project overview
- `requirements.txt` — dependencies list

### What does NOT exist yet
- No Python code written yet
- No database created
- No `config/`, `bot/`, `agent/`, `providers/`, `tools/` directories

---

## Implementation Stages

| # | Title | Status | Notes |
|---|-------|--------|-------|
| 1 | Infrastructure + Bot UI | 🔲 TODO | `refagent.py`, aiogram, animator, LLM providers, model browser |
| 2 | Session management | 🔲 TODO | Load .session files, check UID, SQLite db |
| 3 | AI Agent Core + Telegram tools | 🔲 TODO | ReAct loop, plan manager, tg_tools, conductor, library |

---

## Two Separate Agents — Important Distinction

This project has TWO distinct "agents" — do not confuse them:

### 1. Replit coding agent (you, in this session)
- Writes Python code for RefAgent
- Updates `docs/CONTEXT.md` at end of session
- Pushes to GitHub via API
- Knows about SOLID, aiogram, architecture

### 2. RefAgent's internal AI (LLM inside the running bot)
- Called via OpenRouter or FavoriteAPI
- Runs the ReAct loop to control Telegram accounts
- Gets its rules from `agent/system_prompt.py` (always injected)
- Updates `data/library/*.md` when it finds new error solutions
- Never touches `docs/` folder

---

## Key Design Decisions (summary)

1. **Entry point:** `python refagent.py` → interactive token prompt → bot starts
2. **One LLM at a time** — FavoriteAPI is single-session, no concurrent calls
3. **Conductor always required** — 0% of accounts could DM bots directly in testing
4. **api_id/api_hash per account** — read from sidecar .json, never shared
5. **Sequential referral execution** — 60s hard limit between credits
6. **Library-first error handling** — agent checks `data/library/` before solving
7. **Agent can write temp scripts** — `terminal_tools.py` allows arbitrary Python
8. **FavoriteAPI context management** — auto-compress >150KB, auto-reset at limit

---

## Environment Variables Needed

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `FAVORITEAPI_KEY` | FavoriteAPI key |
| `FAVORITEAPI_URL` | ngrok/tunnel URL |
| `GITHUB_TOKEN` | GitHub personal access token |

**Bot token:** entered interactively at startup, stored in `config.json` locally.

---

## End of Session Checklist (for Replit agent)

- [ ] Mark completed stages in the table above
- [ ] Update "What exists right now" section
- [ ] Add any new architecture decisions or gotchas
- [ ] Push all changes to GitHub
- [ ] Tell user to copy HANDOFF_PROMPT.md for next session
