# RefAgent — Session Context

> **NEW SESSION? Read this file first, then read docs/ARCHITECTURE.md**
> This file is updated at the end of every Replit session.

---

## Current State

**Last updated:** 2026-06-11
**Session:** #1 (planning & design)
**Stage:** Pre-implementation — all design decisions made, ready to build

### What exists right now
- `plan.txt` — master plan with all 8 blocks
- `docs/ARCHITECTURE.md` — deep architecture decisions
- `docs/KNOWLEDGE_BASE.md` — all Telegram gotchas from real testing
- `docs/HANDOFF_PROMPT.md` — prompt to paste in new session
- `README.md` — full project overview

### What does NOT exist yet
- No Python code written yet
- No database created
- No requirements.txt yet

---

## Implementation Stages

| # | Title | Status | Notes |
|---|-------|--------|-------|
| 1 | Infrastructure + Bot UI | 🔲 TODO | Entry point, aiogram, animator, LLM providers, model browser |
| 2 | Session management | 🔲 TODO | Load .session files, check UID, SQLite db |
| 3 | AI Agent Core + Telegram tools | 🔲 TODO | ReAct loop, plan manager, tg_tools, conductor, library |

---

## Key Design Decisions (summary)

1. **Entry point:** `python refagent.py` → interactive token prompt → bot starts
2. **One LLM at a time** (not parallel) — FavoriteAPI is single-session
3. **Conductor always required** — 0% of accounts could DM bots directly in testing
4. **api_id/api_hash per account** — read from sidecar .json, never shared
5. **Sequential referral execution** — 60s hard limit between credits
6. **Library-first error handling** — agent checks /data/library/ before solving
7. **Agent can write temp scripts** — terminal_tools.py allows arbitrary Python execution
8. **FavoriteAPI context management** — auto-compress at >150KB, auto-reset at limit

---

## Environment Variables Needed

| Variable | Description | Where to get |
|----------|-------------|--------------|
| `OPENROUTER_API_KEY` | OpenRouter API key | openrouter.ai |
| `FAVORITEAPI_KEY` | FavoriteAPI key | your FavoriteAPI dashboard |
| `FAVORITEAPI_URL` | FavoriteAPI endpoint | your ngrok/tunnel URL |
| `GITHUB_TOKEN` | GitHub personal token | github.com/settings/tokens |

**Bot token:** entered interactively at startup (stored in `config.json` locally, never in env)

---

## Next Session: Start Here

1. Read this file (CONTEXT.md)
2. Read docs/ARCHITECTURE.md for deep details
3. Check which stage to implement next (table above)
4. Start with the first TODO stage

Or paste the handoff prompt from `docs/HANDOFF_PROMPT.md` directly.
