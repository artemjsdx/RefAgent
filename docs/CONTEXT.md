# RefAgent — Session Context

> **НОВАЯ СЕССИЯ? Сначала прочитай этот файл, потом docs/ARCHITECTURE.md**
>
> **КТО ОБНОВЛЯЕТ:** Replit coding agent обновляет этот файл в конце каждой сессии разработки.
> RefAgent (внутренний LLM) этот файл НЕ трогает.

---

## Текущее состояние

**Последнее обновление:** 2026-06-11
**Сессия:** #3 (Этап 2: Управление сессиями)
**Этап:** Этапы 1 и 2 завершены

### Что существует сейчас

| Файл | Статус | Примечания |
|------|--------|-----------|
| `refagent.py` | Готово | Ввод токена → init_db → aiogram запуск |
| `config/constants.py` | Готово | Все magic numbers, пути, тайминги |
| `config/settings.py` | Готово | BotConfig (config.json) + EnvConfig (env), синглтон |
| `providers/base.py` | Готово | Абстракция BaseProvider, все dataclass |
| `providers/openrouter.py` | Готово | Chat + список моделей (кэш 1ч) |
| `providers/favoriteapi.py` | Готово | Chat + asyncio.Lock + context_kb |
| `providers/__init__.py` | Готово | build_provider(settings) фабрика |
| `bot/ui/animator.py` | Готово | Animator: 9 наборов фреймов, start/finalize |
| `bot/ui/status_blocks.py` | Готово | send_log, send_error, build_task_report |
| `bot/keyboards/main_menu.py` | Готово | Главное меню, настройки, task controls |
| `bot/keyboards/model_browser.py` | Готово | Пагинированный браузер моделей |
| `bot/keyboards/session_menu.py` | Готово | Список сессий, детали, назначение проводника |
| `bot/handlers/start.py` | Готово | /start, приветствие, роутинг (без CB_SESSIONS) |
| `bot/handlers/settings_menu.py` | Готово | Провайдер, модель, тест подключения, guard |
| `bot/handlers/sessions.py` | Готово | Приём файлов, список, детали, conductor |
| `tools/db.py` | Готово | aiosqlite CRUD, UNIQUE api_id, DuplicateApiIdError |
| `tools/session_tools.py` | Готово | detect_format, sidecar JSON, UID, ZIP распаковка |
| `agent/state.py` | Готово | AgentState singleton (is_active флаг) |
| `data/library/*.md` | Готово | 8 записей: ошибки, UID, форматы сессий |
| `.gitignore` | Готово | Исключает sessions, db, config.json |

### Чего ещё НЕТ (следующие этапы)

**Этап 3: AI Agent Core + Telegram инструменты**
- `agent/react_loop.py` — ReAct цикл
- `agent/system_prompt.py` — системный промпт с инструментами
- `tools/telegram_tools.py` — Telethon инструменты
- Harold conductor pattern исполнение
- Чат с агентом в боте (сейчас заглушка)

---

## Этапы разработки

| # | Название | Статус | Примечания |
|---|---------|--------|-----------|
| 1 | Инфраструктура + Bot UI | ГОТОВО | refagent.py, aiogram, animator, провайдеры LLM |
| 2 | Управление сессиями | ГОТОВО | SQLite БД, загрузка .zip/.session, conductor |
| 3 | AI Agent Core + Telegram tools | TODO | ReAct loop, system prompt, Telethon tools |

---

## Два отдельных агента — важное различие

### 1. Replit coding agent (этот)
- Пишет Python код для RefAgent
- Обновляет `docs/CONTEXT.md` в конце сессии
- Пушит на GitHub

### 2. Внутренний AI RefAgent (LLM внутри запущенного бота)
- Вызывается через OpenRouter или FavoriteAPI
- Выполняет ReAct цикл управляя Telegram аккаунтами
- Получает правила из `agent/system_prompt.py`
- Обновляет `data/library/*.md` при нахождении новых решений ошибок
- Никогда не трогает `docs/`

---

## Ключевые архитектурные решения

1. **Токен бота** — вводится интерактивно, хранится в `config.json`, никогда не в env
2. **api_id/api_hash** — ОБЯЗАТЕЛЬНО уникальный на каждый аккаунт из sidecar .json
3. **UNIQUE index на api_id** — жёсткий запрет в БД, `DuplicateApiIdError` при нарушении
4. **Один проводник** — `set_conductor(id, True)` сначала снимает флаг у всех остальных
5. **Guard при активном агенте** — `_agent_active_notice()` блокирует смену провайдера/модели
6. **Animator через dependency injection** — `set_animator()` вызывается из `refagent.py`
7. **Роутер sessions включается ДО start** — чтобы `CB_SESSIONS` не перехватывал заглушку

---

## Паттерны кода которым следовать

```python
# ПРАВИЛЬНО: загрузка сессии
result = await load_session_file(path)
if not result.ok:
    await send_error(bot, chat_id, result.error)

# ПРАВИЛЬНО: проверка api_id дубликата
try:
    acc_id = await add_account(record)
except DuplicateApiIdError as e:
    # Показать жёсткое предупреждение пользователю
    await send_error(bot, chat_id, str(e))

# ПРАВИЛЬНО: Telethon клиент с уникальными credentials
import json
creds = json.loads(Path(session_path).with_suffix('.json').read_text())
client = TelegramClient(session_path, creds['app_id'], creds['app_hash'])

# ПРАВИЛЬНО: random_id
import os
random_id = int.from_bytes(os.urandom(8), 'big', signed=True)
```

---

## Переменные окружения

| Переменная | Описание |
|-----------|---------|
| `OPENROUTER_API_KEY` | API ключ OpenRouter |
| `FAVORITEAPI_KEY` | API ключ FavoriteAPI |
| `FAVORITEAPI_URL` | URL ngrok/tunnel к self-hosted инстансу |
| `GITHUB_TOKEN` | GitHub PAT для пуша в репозиторий |

**Токен бота:** вводится интерактивно при старте, хранится в `config.json` локально.

---

## Как запустить

```bash
cd RefAgent
python refagent.py
# Введи токен бота (Enter = оставить существующий)
```

---

## Контрольный список конца сессии

- [x] Обновить таблицу этапов
- [x] Обновить "Что существует сейчас"
- [x] Добавить архитектурные решения
- [x] Запушить на GitHub
