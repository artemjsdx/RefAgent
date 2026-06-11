# RefAgent

> Autonomous Telegram referral agent with AI ReAct loop, Telethon session management, and knowledge library.

**Status:** In development | **Language:** Python 3.11+ | **Platform:** Termux (Android) / Linux

---

## What it does

RefAgent is an AI agent you talk to via a Telegram bot. You give it a referral link and describe the conditions for earning a referral (subscribe to channels, click buttons, run /verify, etc.). The agent takes a pool of Telegram accounts and autonomously executes the referral chain for each one.

## How it works

```
You (Telegram) → Bot UI → AI Agent (ReAct loop) → Telethon tools → Telegram accounts
                                    ↕
                            Knowledge Library (error solutions)
                                    ↕
                             SQLite (sessions, results)
```

**ReAct loop:** Think → call tool → observe result → think again → ... → final report

---

## Stack

- **Bot UI:** aiogram 3
- **AI Providers:** OpenRouter (300+ models) + FavoriteAPI (Gemini bridge)
- **Telegram control:** Telethon (MTProto)
- **DB:** SQLite (aiosqlite)
- **Target platform:** Termux on Android

---

## Project Structure

```
RefAgent/
├── refagent.py                 # Entry point — run this
├── requirements.txt
├── config/
│   ├── settings.py             # Config loader (env + config.json)
│   └── constants.py            # All timeouts, limits, paths
├── bot/                        # Telegram Bot UI (aiogram 3)
│   ├── handlers/               # start, chat, sessions, settings, stats
│   ├── keyboards/              # main_menu, model_browser, task_controls
│   └── ui/                     # animator, status_blocks, report
├── agent/                      # AI Agent Core
│   ├── react_loop.py           # Think → Act → Observe cycle
│   ├── plan_manager.py         # Create/update/delete plan
│   ├── system_prompt.py        # Build system prompt with rules + plan
│   ├── tools_registry.py       # Register tools for LLM
│   └── context_manager.py      # FavoriteAPI context tracking
├── providers/                  # LLM providers
│   ├── base.py                 # Abstract provider
│   ├── openrouter.py           # OpenRouter (300+ models, paginated)
│   └── favoriteapi.py          # FavoriteAPI (Gemini, memory tags)
├── tools/                      # Agent tools (called by ReAct loop)
│   ├── session_tools.py        # Load sessions, check UID, detect format
│   ├── tg_tools.py             # join_channel, start_bot, click_button
│   ├── conductor_tools.py      # Harold pattern: create_group, invite
│   ├── warmup_tools.py         # Account warmup automation
│   ├── terminal_tools.py       # Shell commands, temp scripts
│   └── library_tools.py        # Search/write knowledge library
├── data/
│   ├── sessions/               # .session files
│   ├── library/                # Error knowledge base (markdown files)
│   ├── sessions.db             # Accounts: uid, api_id, api_hash, status
│   └── results.db              # Task history and results
└── docs/
    ├── CONTEXT.md              # Current session state (read first!)
    ├── ARCHITECTURE.md         # Deep architecture notes
    ├── KNOWLEDGE_BASE.md       # All known Telegram gotchas
    └── HANDOFF_PROMPT.md       # Prompt to paste in new Replit session
```

---

## Critical Rules (baked into agent system prompt)

### ⚠️ Rule 1 — api_id / api_hash MUST be unique per account
Never reuse the same `api_id`/`api_hash` across multiple Telegram accounts.
Each `.session` file must connect with its own credentials from the sidecar `.json`.
**Violation = mass account freeze. Irreversible.**

### ⚠️ Rule 2 — Conductor (Harold pattern) is always required
100% of tested accounts (even old ones) cannot DM bots directly.
Always use the conductor pattern: conductor creates group with bot → fresh account joins via invite → interaction happens in group.

### ⚠️ Rule 3 — Timings are hard limits
- 60s between referral credits (same referrer)
- 15–30s between accounts
- 5s after /start or /verify before reading response

### ⚠️ Rule 4 — Plan before action
Agent must always build and show a plan before starting work.
Plan can be modified during execution with user notification.

---

## Quick Start (Termux)

```bash
# 1. Clone
cd /storage/emulated/0/Цхранилище/Project
git clone https://github.com/artemjsdx/RefAgent.git
cd RefAgent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python refagent.py
# → Will ask for bot token (Enter = keep existing)
# → Bot starts, open Telegram and find your bot
```

---

## Development Progress

See [docs/CONTEXT.md](docs/CONTEXT.md) for current session state.

| Stage | Description | Status |
|-------|-------------|--------|
| 1 | Infrastructure + Bot UI | 🔲 Pending |
| 2 | Session management | 🔲 Pending |
| 3 | AI Agent Core + Telegram tools | 🔲 Pending |

---

## License

MIT — open source, use freely.
