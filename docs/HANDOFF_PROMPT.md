# RefAgent — Universal Session Handoff Prompt

Copy the block below and paste it as your FIRST message in a new Replit session.
Replace the values in [BRACKETS] with your actual keys.

---

```
Ты продолжаешь разработку проекта RefAgent.

ПЕРВЫМ ДЕЛОМ:
1. Склонируй или обнови репозиторий:
   git clone https://github.com/artemjsdx/RefAgent.git
   или если уже есть: git pull origin main

2. Прочитай docs/CONTEXT.md — там текущее состояние проекта
3. Прочитай docs/ARCHITECTURE.md — архитектурные решения
4. Посмотри какой этап следующий в CONTEXT.md и начни его реализацию

КЛЮЧИ (подставь свои):
- OPENROUTER_API_KEY = [твой ключ openrouter]
- FAVORITEAPI_KEY = [твой ключ favoriteapi]  
- FAVORITEAPI_URL = [твой ngrok/tunnel URL]
- GITHUB_TOKEN = [твой github токен]
- BOT_TOKEN = [токен телеграм бота от @BotFather]

Сохрани их как секреты Replit перед началом работы.

ВАЖНЫЕ ПРАВИЛА ПРОЕКТА (никогда не нарушать):
1. Каждый Telegram аккаунт = свой api_id и api_hash. Никогда не шарить между аккаунтами.
2. Conductor (Harold pattern) обязателен — 0% аккаунтов могут DM боту напрямую.
3. Тайминг: 60с между зачислениями рефов, 15-30с между аккаунтами.
4. Код по SOLID, комментарии блоками в коде, чисто и архитектурно.
5. После каждой сессии обновить docs/CONTEXT.md и запушить на GitHub.

СТИЛЬ КОДА:
- Python 3.11+, async/await везде
- Комментарии блоками: # ════════ SECTION NAME ════════
- Никаких magic numbers — всё в config/constants.py
- Каждый файл начинается с docstring описывающего его роль
- Структура: RefAgent/ папка в корне workspace

После прочтения CONTEXT.md скажи мне: какой этап следующий и что будешь делать.
Потом сразу начинай — не нужно дополнительного подтверждения.
```

---

## What to do at end of each session

Before closing Replit, run:

```bash
cd RefAgent
git add -A
git commit -m "Session #N: [brief description of what was done]"
git push origin main
```

And update `docs/CONTEXT.md`:
- Mark completed stages ✅
- Add notes about what works and what doesn't
- Update "What exists right now" section
