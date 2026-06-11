# RefAgent — Session Context

> **НОВАЯ СЕССИЯ? Сначала прочитай этот файл, потом docs/ARCHITECTURE.md**
>
> **КТО ОБНОВЛЯЕТ:** Replit coding agent обновляет этот файл в конце каждой сессии разработки.
> RefAgent (внутренний LLM) этот файл НЕ трогает.

---

## Текущее состояние

**Последнее обновление:** 2026-06-11
**Сессия:** #4 (Этап 3: AI Agent Core — завершён, бот запущен)
**Этап:** Этапы 1, 2 и 3 завершены

### Что существует сейчас

| Файл | Статус | Примечания |
|------|--------|-----------|
| `refagent.py` | Готово | Ввод токена → init_db → init_results_db → aiogram запуск |
| `config/constants.py` | Готово | BAI_* добавлены, все magic numbers |
| `config/settings.py` | Готово | BotConfig + EnvConfig (bai_api_key), синглтон |
| `providers/base.py` | Готово | Абстракция BaseProvider |
| `providers/openrouter.py` | Готово | Chat + список моделей (кэш 1ч) |
| `providers/favoriteapi.py` | Готово | Chat + asyncio.Lock + context_kb |
| `providers/bai.py` | Готово | b.ai OpenAI-compatible, бесплатные модели |
| `providers/__init__.py` | Готово | build_provider с b.ai поддержкой |
| `bot/ui/animator.py` | Готово | Animator: 9 наборов фреймов |
| `bot/ui/status_blocks.py` | Готово | send_log, send_error, build_task_report |
| `bot/ui/report.py` | Готово | send_final_report, save_task_result, get_stats |
| `bot/keyboards/main_menu.py` | Готово | CB_PROVIDER_BAI, plan_confirm, task_controls |
| `bot/keyboards/model_browser.py` | Готово | Пагинированный браузер моделей |
| `bot/keyboards/session_menu.py` | Готово | Список сессий, conductor |
| `bot/handlers/start.py` | Готово | /start, приветствие (CB_STATS — заглушка) |
| `bot/handlers/settings_menu.py` | Готово | Провайдер (3 варианта), модель, тест |
| `bot/handlers/sessions.py` | Готово | Приём файлов, список, conductor |
| `bot/handlers/chat.py` | Готово | FSM: dialog→plan→running→stopped |
| `tools/db.py` | Готово | aiosqlite CRUD, DuplicateApiIdError |
| `tools/session_tools.py` | Готово | detect_format, sidecar JSON, ZIP |
| `tools/tg_tools.py` | Готово | Telethon: connect, join, start_bot, click_button |
| `tools/conductor_tools.py` | Готово | Harold pattern: setup/join/cleanup |
| `tools/library_tools.py` | Готово | search_library, write_library |
| `tools/terminal_tools.py` | Готово | execute_command, run_temp_script |
| `agent/state.py` | Готово | AgentState singleton (is_active) |
| `agent/context_manager.py` | Готово | FavoriteAPI ctx: warn/compress/reset |
| `agent/plan_manager.py` | Готово | PlanManager: create/update/advance/cancel |
| `agent/react_loop.py` | Готово | ReAct цикл: OpenRouter native + FavoriteAPI text |
| `agent/system_prompt.py` | Готово | CRITICAL_RULES + ROLE + tools text |
| `agent/tools_registry.py` | Готово | 16 инструментов: tg + conductor + library + terminal |
| `data/library/*.md` | Готово | 9 записей |
| `config.json` | Готово | Локально, в .gitignore |

### Чего ещё НЕТ (следующие этапы)

**Этап 4: Доработки**
- `bot/handlers/stats.py` — CB_STATS handler (сейчас заглушка в start.py)
- Rate limiter между аккаунтами/рефералами с обратным отсчётом
- `tools/github_push.py` — auto-push после задачи

---

## Этапы разработки

| # | Название | Статус | Примечания |
|---|---------|--------|-----------|
| 1 | Инфраструктура + Bot UI | ГОТОВО | refagent.py, aiogram, animator, провайдеры LLM |
| 2 | Управление сессиями | ГОТОВО | SQLite БД, загрузка .zip/.session, conductor |
| 3 | AI Agent Core + Telegram tools | ГОТОВО | ReAct loop, system prompt, Telethon tools, b.ai |
| 4 | Доработки: stats, rate-limit, github push | TODO | — |

---

## Два отдельных агента — важное различие

### 1. Replit coding agent (этот)
- Пишет Python код для RefAgent
- Обновляет `docs/CONTEXT.md` в конце сессии
- Пушит на GitHub

### 2. Внутренний AI RefAgent (LLM внутри запущенного бота)
- Вызывается через OpenRouter / FavoriteAPI / b.ai
- Выполняет ReAct цикл управляя Telegram аккаунтами
- Никогда не трогает `docs/`

---

## Ключевые архитектурные решения

1. **Токен бота** — вводится интерактивно, хранится в `config.json`, никогда не в env
2. **api_id/api_hash** — ОБЯЗАТЕЛЬНО уникальный на каждый аккаунт из sidecar .json
3. **UNIQUE index на api_id** — жёсткий запрет в БД, `DuplicateApiIdError` при нарушении
4. **Один проводник** — `set_conductor(id, True)` сначала снимает флаг у всех остальных
5. **Guard при активном агенте** — `_agent_active_notice()` блокирует смену провайдера/модели
6. **Animator через dependency injection** — `set_animator()` вызывается из `refagent.py`
7. **Роутер chat включается ДО settings** — чтобы FSM ChatStates не конфликтовал
8. **b.ai провайдер** — OpenAI-compatible, base URL https://api.b.ai/v1, бесплатные: kimi-k2.5, glm-5, glm-5.1, minimax-m2.5
9. **Context manager FavoriteAPI** — warn at 150KB, compress via write:ctx, reset at 180KB

---

## Паттерны кода которым следовать

```python
# ПРАВИЛЬНО: Harold conductor
result = await conductor_setup("botusername")
if not result["ok"]:
    await log_cb(f"❌ {result['error']}")
    return

# ПРАВИЛЬНО: random_id
import os
random_id = int.from_bytes(os.urandom(8), 'big', signed=True)

# ПРАВИЛЬНО: invite hash regex (включает дефис!)
INVITE_HASH_RE = re.compile(r"t\.me/(?:\+|joinchat/)([A-Za-z0-9_-]+)")

# ПРАВИЛЬНО: загрузка сессии
result = await load_session_file(path)
if not result.ok:
    await send_error(bot, chat_id, result.error)
```

---

## Переменные окружения (Replit secrets)

| Переменная | Описание |
|-----------|---------|
| `OPENROUTER_API_KEY` | API ключ OpenRouter |
| `FAVORITEAPI_KEY` | API ключ FavoriteAPI |
| `FAVORITEAPI_URL` | URL ngrok/tunnel |
| `GITHUB_TOKEN` | GitHub PAT для пуша |
| `BAI_API_KEY` | b.ai API ключ |

**Токен бота:** в `config.json`, НЕ в env.

---

## Как запустить (Replit)

Бот настроен как Replit workflow "RefAgent Bot" — запускается автоматически.

Вручную:
```bash
cd RefAgent
python3 refagent.py
```

---

## Контрольный список конца сессии

- [x] Обновить таблицу этапов
- [x] Обновить "Что существует сейчас"
- [x] Добавить архитектурные решения
- [x] Запушить на GitHub
