# RefAgent — Universal Session Handoff Prompt

Copy the block below and paste it as your FIRST message in a new Replit session.
Replace values in [BRACKETS] with your actual keys.

---

```
Ты продолжаешь разработку проекта RefAgent на Replit.

ПЕРВЫМ ДЕЛОМ (до любого кода):
1. Прочитай https://raw.githubusercontent.com/artemjsdx/RefAgent/main/docs/CONTEXT.md
2. Прочитай https://raw.githubusercontent.com/artemjsdx/RefAgent/main/docs/ARCHITECTURE.md
3. Посмотри таблицу этапов в CONTEXT.md — найди первый TODO и начни его

КЛЮЧИ (сохрани как Replit Secrets перед началом):
- OPENROUTER_API_KEY = [вставь]
- FAVORITEAPI_KEY = [вставь]
- FAVORITEAPI_URL = [вставь ngrok/tunnel URL]
- GITHUB_TOKEN = [вставь]
- В файле config.json или при запуске: BOT_TOKEN = [токен @BotFather]

КОД — ОБЯЗАТЕЛЬНЫЙ СТИЛЬ:
- Python 3.11+, async/await везде
- Комментарии блоками: # ════════ SECTION NAME ════════
- Никаких magic numbers — всё в config/constants.py
- Каждый файл начинается с docstring описывающего его роль
- Структура: RefAgent/ папка в корне workspace

В КОНЦЕ КАЖДОЙ СЕССИИ (делает Replit-агент, то есть ты):
1. Обнови docs/CONTEXT.md — отметь завершённые этапы, добавь заметки
2. Запушь все изменения на GitHub через GitHub API
3. Напомни пользователю скопировать handoff-промпт для следующей сессии
```

---

## Что НЕ входит в этот промпт

Правила для **реферального агента** (api_id уникальность, conductor, тайминги и т.д.)
живут в `agent/system_prompt.py` и всегда передаются **внутреннему LLM-агенту RefAgent**
при каждом запросе. Это не задача Replit-сессии — это часть кода самого RefAgent.

---

## Кто что обновляет

| Файл | Кто обновляет | Когда |
|------|--------------|-------|
| `docs/CONTEXT.md` | Replit-агент (я) | В конце каждой coding-сессии |
| `docs/ARCHITECTURE.md` | Replit-агент | При смене архитектурных решений |
| `docs/KNOWLEDGE_BASE.md` | Replit-агент | При добавлении новых telegram-знаний |
| `agent/system_prompt.py` | Код RefAgent | Всегда передаётся ReAct-агенту |
| `data/library/*.md` | ReAct-агент внутри RefAgent | При обнаружении новых ошибок в работе |
