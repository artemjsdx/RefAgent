# CONTEXT.md — RefAgent Project State
_Last updated: Session #5 (2026-06-11)_

## Что такое RefAgent
Telegram-бот на Python (aiogram 3) + ReAct-агент (Telethon) для автоматизации реферальных задач.
Harold Conductor pattern — один «проводник» управляет несколькими рабочими аккаунтами.

---

## Статус по этапам

### ✅ Этап 1 — База проекта
- refagent.py, config/, db/, bot/ структура
- aiogram polling, SQLite, env secrets

### ✅ Этап 2 — Провайдеры LLM
- providers/openrouter.py — OpenAI-compatible, auto-fallback на 429
- providers/bai.py — OpenAI-compatible (b.ai)
- providers/favoriteapi.py — Gemini bridge через Telegram (/api/v1/chat)

### ✅ Этап 3 — ReAct loop + Harold Conductor
- agent/react_loop.py — Think→Act→Observe, 50 итераций макс
- agent/plan_manager.py — propose_plan → execute
- tools/tg_tools.py — connect/join/start_bot/send_message/click_button
- tools/conductor_tools.py — Harold pattern
- tools/library_tools.py — поиск/запись в базу знаний
- tools/terminal_tools.py — execute_command, run_temp_script

### ✅ Этап 4 — Тестирование (Session #5)
#### 🎯 Целевое минное поле
- @RefTestRef8483_bot (token: 8901857239:AAGwuUvNQ2iB9ahew4dQ8Ybr2HHvAZTCKno)
- RefTest Channel (ID: -1003703314975, invite: https://t.me/+7EGLjx54um42ZGQx)
- Механика: /start?start=UID → проверка подписки → реферал засчитывается
- Workflow: "RefTest Target Bot" — RUNNING

#### 📊 Результаты тестов провайдеров (все PASS)
| Провайдер | Модель | L1 Health | L2 Chat | L3 ReAct | Время L3 |
|-----------|--------|-----------|---------|----------|----------|
| OpenRouter | openai/gpt-oss-20b:free | ✅ | ✅ | ✅ | 2.7s |
| b.ai | kimi-k2.5 | ✅ | ✅ | ✅ | 3.6s |
| FavoriteAPI | gemini-3.0-flash-thinking | ✅ | ✅ | ✅ | 44s |

**OpenRouter fix:** auto-fallback список при 429 (gemma-4-26b rate-limited → gpt-oss-20b работает)
**FavoriteAPI:** правильный endpoint /api/v1/chat (не /chat/completions), ответ за ~10s

#### 🔌 Аккаунты
| Роль | Телефон | UID | Статус |
|------|---------|-----|--------|
| Harold Conductor | +14707620517 | 8978062324 | ✅ Подключён, создал бота/канал |
| RefAgent #1 | +14707526421 | 8889003554 | ✅ Anthony — подключается |
| RefAgent #2 | +14707526481 | 8828859030 | ✅ Matthew — подключается |
| RefAgent #3 | +14707526490 | 8801963564 | ✅ Richard — подключается |
| Test victim #1 | +14707621165 | ? | Готов |
| Test victim #2 | +14707621178 | ? | Готов |
| Test victim #3 | +14707621741 | ? | Готов |
| Test victim #4 | +14707624448 | ? | Готов |

---

## Работающие боты (Replit Workflows)
- **@TestAIReZero_bot** — RefAgent Bot (provider: openrouter, model: openai/gpt-oss-20b:free)
- **@RefTestRef8483_bot** — RefTest Target Bot (минное поле для тестов)

---

## Известные баги / TODO
- [ ] Referral blast: ImportChatInviteRequest — проверить работу (v2 запускается)
- [ ] CB_STATS handler в RefAgent боте не реализован
- [ ] Rate limiter 20s/60s нет обратного отсчёта в UI
- [ ] FavoriteAPI context_kb не обновляется в /api/v1/me после reset

---

## Файлы
```
RefAgent/
├── refagent.py              — точка входа
├── requirements.txt         — зависимости (Termux)
├── run.sh                   — запуск в Termux/Linux
├── .env.example             — шаблон .env
├── README-TERMUX.md         — инструкция для Termux
├── config/
│   ├── constants.py
│   ├── settings.py
│   ├── config.json          — {active_provider, active_model}
│   └── accounts.json        — аккаунты по ролям
├── agent/                   — ReAct loop, prompts, tools registry
├── providers/               — openrouter, bai, favoriteapi
├── tools/                   — tg_tools, conductor, library, terminal
├── bot/                     — aiogram handlers, keyboards, UI
├── target_bot/              — @RefTestRef8483_bot (минное поле)
├── tests/
│   ├── test_providers.py    — L1/L2/L3 тесты всех провайдеров
│   └── test_referral_blast.py — реальная накрутка 3 аккаунтами
└── data/sessions/           — .session + .json sidecar (9 аккаунтов)
```

---

## API ключи (в Replit Secrets)
- OPENROUTER_API_KEY — OpenRouter (~$0.6 остаток)
- BAI_API_KEY — b.ai (500K токенов free)
- FAVORITEAPI_KEY — FavoriteAPI (Gemini bridge, fa_sk_...)
- FAVORITEAPI_URL — ngrok/CF tunnel URL
- GITHUB_TOKEN — для auto-push
- BOT_TOKEN — через env (не в config.json)
