# CONTEXT.md — RefAgent Project State
_Last updated: Session #10 (2026-06-13) — Clear History button + Export/Import chat_

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

### ✅ Этап 8 — Chat Edit + Model Browser (Session #8)

#### Цель: закрыть все TODO из Этапа 6/7

#### 1. OpenRouter default model обновлён
| Файл | Изменение |
|------|-----------|
| `providers/openrouter.py` | `OPENROUTER_DEFAULT_MODEL = "deepseek/deepseek-r1-0528:free"` |
| | Новый fallback chain: deepseek-r1 → deepseek-chat-v3 → gemma-3-27b → gemma-4-31b → llama-4-scout |

#### 2. Браузер моделей в new_chat FSM (OpenRouter)
При создании чата с OpenRouter шаг "Выбери модель" теперь показывает:
- 📋 Бесплатные / 💳 Платные — paginated список (10/страница)
- ⌨️ Ввести ID вручную
- ⏭ Пропустить (deepseek-r1:free по умолчанию)

Callback prefix: `ncm:` (New Chat Model) — изолирован от settings browser (`models:`).

Файлы:
| Файл | Изменение |
|------|-----------|
| `bot/handlers/new_chat.py` | `_ask_model()` — OpenRouter показывает браузер; callbacks `ncm:free/paid/select/manual/noop` |

#### 3. Редактирование настроек существующего чата
Новая кнопка **✏️ Изменить** в деталях чата (рядом с 💬 Открыть).

FSM `ChatEditStates`:
- `choosing_field` — меню: Название / API ключ / Модель
- `editing_name` — ввод нового названия
- `editing_apikey` — ввод нового ключа (с auto-delete сообщения)
- `editing_model` — ввод модели или браузер (OpenRouter: free/paid pages)
- `browsing_model` — browsing state (зарезервировано)

Файлы:
| Файл | Изменение |
|------|-----------|
| `bot/handlers/chat_edit.py` | НОВЫЙ: полный FSM редактирования |
| `bot/keyboards/chat_keyboards.py` | +`CB_CHAT_EDIT`, кнопка ✏️ в `chat_detail_keyboard` |
| `tools/chat_db.py` | +`update_chat_fields(**fields)` — универсальный UPDATE |
| `refagent.py` | +`chat_edit_router` в `register_handlers()` |

---

## Работающие боты (Replit Workflows)
- **@TestAIReZero_bot** — RefAgent Bot (per-chat API keys, multi-chat)

---

## Кондукторы (НЕ трогать как рабочие)
- `+14707526421` — conductor #1 (из covet.txt)
- `+14707620517` — conductor #2 / Harold (из CONTEXT.md)

---

---

### ✅ Этап 9 — History + Bug Fixes (Session #9)

#### 1. Персистентная история сообщений
| Файл | Изменение |
|------|-----------|
| `tools/history_db.py` | НОВЫЙ: таблица `chat_history`, save_pair/load_history/clear_history |
| `tools/db.py` | `init_db()` создаёт history таблицу + фикс: skill_stats был вне `async with` |
| `bot/handlers/chat.py` | `_load_llm_history()` + `save_pair()` в `handle_dialog_message` |
| `agent/react_loop.py` | `run()` принимает `initial_messages: list[Message]` — инжектируется в историю |

Ключ истории = `chat_record_id` (ID записи в таблице `chats`). Каждый чат имеет независимую историю.

#### 2. Фикс: статус-блок всегда последний
**Проблема:** `send_step`, `send_account`, `send_warn`, `send_error` и др. отправлялись без остановки аниматора → "Thinking..." блок оказывался не последним.

**Фикс:** В `_start_agent_task` добавлен helper `_with_anim(coro, terminal=False)`:
1. Останавливает и удаляет текущий аниматор
2. Выполняет `coro` (отправляет сообщение)
3. Запускает новый аниматор (если не terminal)

Файл: `bot/handlers/chat.py`

#### 3. Фикс: `<tool_call>` теги в сообщениях Telegram
**Причина:** В ветке `else` (нет распознанных тул-коллов) `last_text = response.text` сохранял текст с тегами. Telegram отклонял с `TelegramBadRequest: Unsupported start tag "tool_call"`.

**Фикс:** `last_text = strip_tool_calls(response.text).strip()` — всегда чистим перед отправкой.

Файл: `agent/react_loop.py`

#### 4. Фикс: search_skills / use_skill инструменты
**Причина:** `_dispatch()` не обрабатывал `search_skills`/`use_skill` → возвращал "Unknown tool". Дублирующая сломанная секция в цикле использовала несуществующую переменную `tool_args`.

**Фикс:**
- Добавлены обработчики в `_dispatch()`
- Сломанная post-execution секция skills удалена из цикла
- Остался только `propose_plan` return и `_emit_tool_specific`

Файл: `agent/react_loop.py`

#### 5. Фикс: init_db синтаксические баги
- `skill_stats` CREATE TABLE был вне `async with db:` блока → ошибка при старте
- `system_prompt.py`: двойная запятая в сигнатуре `build_system_prompt()`
- Оба исправлены

#### 6. Улучшенные сообщения об ошибках сессий
**Причина:** "too many values to unpack (expected 5)" — сессия создана с другим клиентом (не Telethon), структура таблицы `sessions` отличается.

**Фикс:** В `_get_client()` перехватываем `ValueError` с "unpack" и показываем понятное сообщение с инструкцией.

Файл: `tools/tg_tools.py`

#### 7. Правило 13 в CRITICAL_RULES
Запрет прямого доступа к SQLite из агента (причина краша: агент пытался `SELECT *` из accounts таблицы и распаковывал в tuple с 5 полями, а там 13).

Файл: `agent/system_prompt.py`

---

---

### ✅ Этап 10 — Clear History + Export/Import (Session #10)

#### 1. Кнопка 🧹 Очистить историю в деталях чата
| Файл | Изменение |
|------|-----------|
| `bot/keyboards/chat_keyboards.py` | +`CB_CHAT_CLEAR_HIST`, +`CB_CHAT_CONFIRM_HIST`, кнопка в `chat_detail_keyboard`, +`confirm_clear_hist_keyboard` |
| `bot/handlers/chat_list.py` | +`cb_clear_hist` — показывает кол-во сообщений + подтверждение; +`cb_confirm_clear_hist` — очищает историю, возвращает в детали |

Нажатие 🧹 показывает сколько сообщений будет удалено. После подтверждения агент начинает диалог с чистого листа.

#### 2. 📤 Экспорт настроек чата
| Файл | Изменение |
|------|-----------|
| `bot/keyboards/chat_keyboards.py` | +`CB_CHAT_EXPORT`, кнопка 📤 Экспорт в `chat_detail_keyboard` |
| `bot/handlers/chat_list.py` | +`cb_export_chat` — отправляет JSON файл с настройками чата |

Формат экспорта (`chat_<name>.json`):
```json
{
  "refagent_chat_export": true,
  "version": 1,
  "name": "Название",
  "provider": "openrouter",
  "api_key": "sk-...",
  "api_url": null,
  "model": "deepseek/deepseek-r1-0528:free"
}
```
**Внимание:** файл содержит API ключ — хранить безопасно.

#### 3. 📥 Импорт чата из JSON файла
| Файл | Изменение |
|------|-----------|
| `bot/handlers/chat_import.py` | НОВЫЙ: хендлер `handle_document` — перехватывает .json файлы с маркером `refagent_chat_export` |
| `refagent.py` | +`chat_import_router` в `register_handlers()` |

Пользователь отправляет .json файл боту → бот парсит, валидирует, создаёт чат → предлагает сразу открыть.
Обычные .json файлы (без маркера) пропускаются, не мешая другим хендлерам.

---

## Известные баги / TODO
- [x] ~~Модель по умолчанию для OpenRouter нужно обновить~~ — обновлена на deepseek-r1-0528:free
- [x] ~~При создании чата — показывать список доступных моделей провайдера~~ — браузер ncm: интегрирован
- [x] ~~Редактирование настроек существующего чата~~ — chat_edit.py, кнопка ✏️ Изменить
- [x] ~~История сообщений чата~~ — history_db.py, персистентна между перезапусками
- [x] ~~Статус-блок не всегда последний~~ — _with_anim helper в chat.py
- [x] ~~`<tool_call>` теги в сообщениях~~ — strip_tool_calls(last_text) в react_loop.py
- [x] ~~search_skills/use_skill не работали~~ — добавлены в _dispatch()
- [x] ~~Кнопка "🧹 Очистить историю" в деталях чата~~ — кнопка в chat_detail_keyboard, хендлер в chat_list.py
- [x] ~~Экспорт/импорт настроек чата~~ — кнопка 📤 Экспорт (JSON файл), импорт через отправку .json боту
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
