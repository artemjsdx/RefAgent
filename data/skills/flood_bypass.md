---
  name: flood_bypass
  title: Обход FloodWait и rate limits
  type: knowledge
  tags: ["flood", "floodwait", "ratelimit", "error", "bypass"]
  scope: global
  active: true
  created: 2026-06-12
  ---

  ## Когда использовать
  При получении FloodWaitError, TooManyRequestsError или любых ошибок rate limiting от Telegram.

  ## Когда НЕ использовать
  Если это другая ошибка (AUTH_KEY, PEER_INVALID и др.) — сначала search_library.

  ## Как применять

  **Алгоритм обработки FloodWait:**

  1. Поймал FloodWaitError(seconds=N):
     - N ≤ 600 → `sleep_seconds(N + 3)` → retry того же действия
     - N > 600 → пропустить аккаунт, записать "flood_too_long:{N}", двигаться дальше

  2. FloodWait при join_channel:
     - Каждый аккаунт получает свой независимый FloodWait
     - asyncio.gather позволяет всем ждать параллельно — итоговое время = max(всех wait)
     - НЕ суммируй FloodWait'ы последовательно

  3. InviteRequestSentError (при вступлении в канал):
     - Это НЕ ошибка — это approval-канал (требует одобрения)
     - Считать как УСПЕХ и продолжать

  4. ChatWriteForbiddenError:
     - Аккаунт не может писать в группу → search_library("ChatWriteForbidden")

  **Превентивные меры:**
  - Пауза 60с между рефералами (правило #4)
  - Пауза 20с между аккаунтами в последовательном режиме
  