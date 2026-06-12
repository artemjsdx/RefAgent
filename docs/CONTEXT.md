# CONTEXT.md — RefAgent Project State
_Last updated: Session #7 (2026-06-12) — Multi-chat UX overhaul complete_

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
- providers/bai.py — OpenAI-compatible (b.ai, kimi-k2.5 / glm-5)
- providers/favoriteapi.py — Gemini bridge через Telegram (/api/v1/chat)

### ✅ Этап 3 — ReAct loop + Harold Conductor
- agent/react_loop.py — Think→Act→Observe, 50 итераций макс
- agent/plan_manager.py — propose_plan → execute
- tools/tg_tools.py — connect/join/start_bot/send_message/click_button
- tools/conductor_tools.py — Harold pattern
- tools/library_tools.py — поиск/запись в базу знаний
- tools/terminal_tools.py — execute_command, run_temp_script

### ✅ Этап 4 — Тестирование (Session #5)
#### 🎯 Тестовое минное поле
- @RefTestRef8483_bot (token: 8901857239:AAGwuUvNQ2iB9ahew4dQ8Ybr2HHvAZTCKno)
- RefTest Channel (ID: -1003703314975, invite: https://t.me/+7EGLjx54um42ZGQx)
- Механика: /start?start=UID → проверка подписки → реферал засчитывается

#### 📊 Результаты тестов провайдеров (все PASS)
| Провайдер | Модель | L1 Health | L2 Chat | L3 ReAct | Время L3 |
|-----------|--------|-----------|---------|----------|----------|
| OpenRouter | openai/gpt-oss-20b:free | ✅ | ✅ | ✅ | 2.7s |
| b.ai | kimi-k2.5 | ✅ | ✅ | ✅ | 3.6s |
| FavoriteAPI | gemini-3.0-flash-thinking | ✅ | ✅ | ✅ | 44s |

#### 🔌 Аккаунты
| Роль | Телефон | UID | Статус |
|------|---------|-----|--------|
| Harold Conductor | +14707620517 | 8978062324 | ✅ Проводник — НЕ использовать как рабочий |
| Conductor #2 (skip) | +14707526421 | 8889003554 | ✅ Anthony — тоже conductor, не трогать |
| RefAgent #1 | +14707526481 | 8828859030 | ✅ Matthew |
| RefAgent #2 | +14707526490 | 8801963564 | ✅ Richard |

---

### ✅ Этап 5 — Рефакторинг из covet.txt (Session #7)

#### Исправления провайдеров
| Файл | Изменение |
|------|-----------|
| `providers/base.py` | Message dataclass: +`tool_calls`, +`tool_call_id` (без них tool calls падали TypeError) |
| `providers/openrouter.py` | `_serialize_message()` — правильная сериализация tool_calls у assistant и tool_call_id у tool |

#### Новые правила системного промпта (rules 9–12)
| # | Правило |
|---|---------|
| 9 | CONCURRENCY = len(accounts) — никогда не батчи по 3-5 |
| 10 | FloodWait MAX 600с; `InviteRequestSentError` = УСПЕХ |
| 11 | MNGF-канал ПЕРВЫМ пока окно чистое |
| 12 | Дубликаты и числовые сессии пропускать; кондукторов не трогать |

#### Библиотека знаний
- `data/library/flood_wait_strategy.md` — FloodWait паттерны и параллельность
- `data/library/telegram_mechanics.md` — UID категории, Harold, таймауты
- `data/library/referral_pattern_general.md` — универсальный алгоритм для любого реф-бота

---

### ✅ Этап 6 — Multi-chat UX overhaul (Session #7)

#### Концепция
Каждый чат хранит собственные `provider`, `api_key`, `model` в SQLite.
В боте нет предзаполненных API ключей — open source.

#### Новая таблица `chats` в sessions.db
```sql
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,    -- Telegram user_id
    name TEXT NOT NULL,          -- пользовательское название
    provider TEXT NOT NULL,      -- openrouter | favoriteapi | bai
    api_key TEXT NOT NULL,       -- хранится per-chat
    api_url TEXT,                -- только FavoriteAPI
    model TEXT,                  -- NULL = provider default
    created_at INTEGER NOT NULL,
    last_used INTEGER
)
```

#### Флоу создания чата (FSM)
```
➕ Новый чат → ввод названия → выбор провайдера → ввод API ключа
→ (для FA: ввод URL) → ввод модели / пропустить → чат создан → dialog
```

#### Новые файлы
| Файл | Описание |
|------|----------|
| `tools/chat_db.py` | ChatRecord dataclass + CRUD: create/get/list/delete/touch |
| `bot/handlers/new_chat.py` | FSM создания чата (NewChatStates: 5 шагов) |
| `bot/handlers/chat_list.py` | Список/просмотр/удаление чатов |
| `bot/keyboards/chat_keyboards.py` | Все клавиатуры для чатов |

#### Обновлённые файлы
| Файл | Изменение |
|------|-----------|
| `tools/db.py` | init_db() создаёт таблицу chats вместе с accounts |
| `providers/__init__.py` | +`build_provider_from_chat(chat)` — провайдер из ChatRecord |
| `bot/handlers/chat.py` | Диалог использует per-chat API ключ через `_load_active_chat()` |
| `bot/handlers/reply_handler.py` | +BTN_MY_CHATS обработчик; check active_chat_id перед dialog |
| `bot/keyboards/main_menu.py` | ➕💬🗄️📊ℹ️ — все кнопки с эмодзи; нет больше глобального CB_CHAT |
| `bot/keyboards/reply_keyboard.py` | BTN_MY_CHATS вместо BTN_STATS; все кнопки с эмодзи |
| `bot/handlers/start.py` | Новый WELCOME_TEXT; CB_CHAT удалён, навигация через inline |
| `refagent.py` | Регистрация new_chat_router и chat_list_router |

#### Фикс анимации
**Баг:** `cycle(frames)` начинал с `"Thinking"` (уже отправлено) → `TelegramBadRequest: message is not modified` → анимация ломалась на первой итерации, пользователь всегда видел "Thinking".

**Фикс:** `next(frames_iter)` пропускает первый фрейм — теперь анимация работает корректно.

Файл: `bot/ui/animator.py` → `_animate()`: добавлен `next(frames_iter)` + `except Exception: break`

---

### ✅ Этап 7 — Starfall blast (Session #7)
- @starfalll_tg_bot — 32 аккаунта параллельно
- 19 🎉 verified + 13 ✅ steps_done + 0 ошибок
- +9 рефов подтверждено пользователем

---

## Работающие боты (Replit Workflows)
- **@TestAIReZero_bot** — RefAgent Bot (per-chat API keys, multi-chat)

---

## Кондукторы (НЕ трогать как рабочие)
- `+14707526421` — conductor #1 (из covet.txt)
- `+14707620517` — conductor #2 / Harold (из CONTEXT.md)

---

## Известные баги / TODO
- [ ] Модель по умолчанию для OpenRouter нужно обновить (текущая бесплатная модель может быть rate-limited)
- [ ] При создании чата — показывать список доступных моделей провайдера
- [ ] Редактирование настроек существующего чата (сейчас только удаление/пересоздание)
- [x] ~~Блок статуса "Thinking" никогда не менялся~~ — исправлено (animator fix)
- [x] ~~Глобальные API ключи в .env~~ — убраны, теперь per-chat
- [x] ~~Нет эмодзи в интерфейсе~~ — добавлены везде
- [x] ~~Rate limiter без обратного отсчёта~~ — исправлено (sleep_with_countdown)

---

## Файловая структура (актуальная)
```
RefAgent/
├── refagent.py              — точка входа
├── config/
│   ├── constants.py
│   ├── settings.py
│   └── config.json
├── agent/
│   ├── react_loop.py
│   ├── plan_manager.py
│   ├── system_prompt.py     — rules 1-12
│   ├── status_event.py
│   ├── state.py
│   ├── context_manager.py
│   └── tools_registry.py
├── providers/
│   ├── __init__.py          — build_provider + build_provider_from_chat
│   ├── base.py              — Message(tool_calls, tool_call_id)
│   ├── openrouter.py        — _serialize_message fix
│   ├── favoriteapi.py
│   └── bai.py
├── tools/
│   ├── chat_db.py           — НОВЫЙ: ChatRecord CRUD
│   ├── db.py                — +chats table в init_db()
│   ├── session_tools.py
│   ├── tg_tools.py
│   ├── conductor_tools.py
│   ├── library_tools.py
│   └── terminal_tools.py
├── bot/
│   ├── handlers/
│   │   ├── new_chat.py      — НОВЫЙ: FSM создания чата
│   │   ├── chat_list.py     — НОВЫЙ: список/управление чатами
│   │   ├── reply_handler.py — +BTN_MY_CHATS
│   │   ├── chat.py          — per-chat provider
│   │   ├── sessions.py
│   │   ├── settings_menu.py
│   │   └── start.py
│   ├── keyboards/
│   │   ├── chat_keyboards.py — НОВЫЙ: chat creation + list keyboards
│   │   ├── main_menu.py      — эмодзи везде
│   │   ├── reply_keyboard.py — BTN_MY_CHATS + эмодзи
│   │   ├── session_menu.py
│   │   └── model_browser.py
│   ├── ui/
│   │   ├── animator.py      — FIX: next(frames_iter) skip first frame
│   │   ├── status_blocks.py
│   │   └── report.py
│   └── file_buffer.py
├── data/
│   ├── sessions/            — .session файлы аккаунтов
│   ├── library/             — база знаний (md файлы)
│   ├── sessions.db          — accounts + chats таблицы
│   └── results.db
└── docs/
    ├── CONTEXT.md           — этот файл
    ├── ARCHITECTURE.md
    └── FAVORITEAPI.md
```
