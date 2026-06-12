# RefAgent

> Autonomous Telegram referral agent — AI ReAct loop + Telethon + multi-chat bot UI.

**Status:** Active development | **Language:** Python 3.11+ | **Platform:** Linux / Termux (Android)

---

## What it does

RefAgent is an AI agent you control via Telegram. Give it a referral link and describe the conditions (subscribe to channels, click buttons, run /verify, etc.). The agent takes a pool of Telegram accounts and autonomously executes the referral chain for each one.

## How it works

```
You (Telegram) → Bot UI → AI Agent (ReAct loop) → Telethon tools → Telegram accounts
                                    ↕
                            Knowledge Library (error solutions)
                                    ↕
                             SQLite (sessions + chats + results)
```

**ReAct loop:** Think → call tool → observe result → think again → ... → final report

---

## Key Features

- **Multi-chat system** — each chat has its own API key, provider, and model (no shared keys)
- **Animated status blocks** — Thinking. Thinking.. Thinking... (live in Telegram)
- **Harold Conductor pattern** — bypass DM restrictions for all account types
- **Knowledge library** — agent learns from errors, saves solutions to markdown files
- **Plan before action** — agent proposes a plan, user confirms before execution

---

## Stack

- **Bot UI:** aiogram 3 (multi-chat FSM, inline keyboards, reply keyboards)
- **AI Providers:** OpenRouter (300+ models) · FavoriteAPI (Gemini bridge) · b.ai (500K free)
- **Telegram control:** Telethon (MTProto)
- **DB:** SQLite (aiosqlite) — accounts + chats + results

---

## Project Structure

```
RefAgent/
├── refagent.py                 # Entry point
├── config/
│   ├── settings.py             # Config loader (env + config.json)
│   └── constants.py            # All timeouts, limits, paths
├── bot/                        # Telegram Bot UI (aiogram 3)
│   ├── handlers/
│   │   ├── new_chat.py         # FSM: create chat (name→provider→key→model)
│   │   ├── chat_list.py        # Chat list, open, delete
│   │   ├── chat.py             # Dialog FSM with agent
│   │   ├── sessions.py         # Session file management
│   │   ├── reply_handler.py    # Reply keyboard intercepts
│   │   └── settings_menu.py
│   ├── keyboards/
│   │   ├── chat_keyboards.py   # Chat creation + list keyboards
│   │   ├── main_menu.py        # Main menu (with emojis)
│   │   └── reply_keyboard.py   # idle/running/plan keyboards
│   └── ui/
│       ├── animator.py         # Status block animation
│       ├── status_blocks.py    # Agent event rendering
│       └── report.py
├── agent/                      # AI Agent Core
│   ├── react_loop.py           # Think → Act → Observe cycle
│   ├── plan_manager.py         # Create/confirm/execute plan
│   ├── system_prompt.py        # Rules 1-12 baked in
│   ├── tools_registry.py
│   └── context_manager.py
├── providers/                  # LLM providers
│   ├── __init__.py             # build_provider_from_chat() factory
│   ├── openrouter.py
│   ├── favoriteapi.py
│   └── bai.py
├── tools/                      # Agent tools (called by ReAct loop)
│   ├── chat_db.py              # ChatRecord CRUD (per-chat API keys)
│   ├── db.py                   # Accounts + chats SQLite
│   ├── tg_tools.py             # join_channel, start_bot, click_button
│   ├── conductor_tools.py      # Harold pattern
│   ├── terminal_tools.py       # Shell + temp scripts
│   └── library_tools.py        # Search/write knowledge base
├── data/
│   ├── sessions/               # .session files (one per account)
│   ├── library/                # Error knowledge base (markdown)
│   ├── sessions.db             # accounts + chats tables
│   └── results.db              # Task history
└── docs/
    ├── CONTEXT.md              # Session state (read first!)
    └── FAVORITEAPI.md
```

---

## Bot UI Flow

### First time
```
/start → main menu
  ➕ Новый чат
    → enter chat name
    → pick provider: 🔀 OpenRouter | ⭐ FavoriteAPI | 💡 b.ai
    → enter API key (stored per-chat, not globally)
    → enter model ID (or skip for default)
    → chat created → start typing your task
```

### Returning user
```
/start → main menu
  💬 Мои чаты → list of named chats
    → tap to open → type task
```

### Agent execution
```
User types task
  → agent thinks (Thinking. Thinking.. animated block)
  → agent proposes plan
  → user confirms → 🚀 Запустить план
  → agent runs parallel across all accounts
  → final report with stats
```

---

## Critical Rules (baked into agent system prompt)

### ⚠️ Rule 1 — api_id / api_hash MUST be unique per account
Never reuse the same `api_id`/`api_hash` across multiple accounts.
**Violation = mass account freeze. Irreversible.**

### ⚠️ Rule 2 — Conductor (Harold pattern) is always required
100% of tested accounts cannot DM bots directly.
Always: conductor creates group with bot → fresh account joins via invite → interaction in group.

### ⚠️ Rule 3 — Timings are hard limits
- 60s between referral credits (same referrer)
- 15–30s between accounts
- 5s after /start or /verify before reading response

### ⚠️ Rule 4 — Plan before action
Agent always proposes a plan before starting. User confirms.

### ⚠️ Rule 5 — Concurrency = all accounts
Never batch 3-5 accounts. Run all accounts in parallel (one asyncio.gather).

### ⚠️ Rule 6 — FloodWait max 600s
`InviteRequestSentError` = success. FloodWait > 600s = skip account.

### ⚠️ Rule 7 — MNGF channel first
Join MNGF-type channels first (no DM restrictions on fresh accounts for group joins).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/artemjsdx/RefAgent.git
cd RefAgent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env with your bot token
echo "BOT_TOKEN=your_token_here" > .env

# 4. Run
python refagent.py
# Bot starts → open Telegram → /start → create a chat → give it a task
```

**API keys are entered per-chat in the bot UI** — no need to add them to .env.

---

## Development Progress

| Stage | Description | Status |
|-------|-------------|--------|
| 1 | Infrastructure + Bot UI | ✅ Done |
| 2 | LLM Providers (OpenRouter / FavoriteAPI / b.ai) | ✅ Done |
| 3 | ReAct loop + Harold Conductor + Telegram tools | ✅ Done |
| 4 | Provider testing (L1/L2/L3 all pass) | ✅ Done |
| 5 | Refactoring (tool_calls fix, new system rules) | ✅ Done |
| 6 | Multi-chat UX (per-chat API keys, emojis, animator fix) | ✅ Done |
| 7 | Starfall blast (32 accounts, 19 verified) | ✅ Done |

---

## License

MIT — open source, use freely.
