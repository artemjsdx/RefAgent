---
  name: ref_standard
  title: Стандартный реферальный прогон
  type: knowledge
  tags: ["ref", "conductor", "standard", "bot"]
  scope: global
  active: true
  created: 2026-06-12
  ---

  ## Когда использовать
  При любой задаче с рефералами через Telegram-бота. Применяй как базовый алгоритм если нет специального навыка для конкретного бота.

  ## Когда НЕ использовать
  Если бот работает без Conductor-группы (прямые сообщения разрешены) — skip conductor_setup. Если есть специальный навык для конкретного бота — используй его вместо этого.

  ## Как применять

  **Harold-паттерн (стандартный):**

  1. `list_accounts` → взять все ACTIVE аккаунты (не кондукторов)
  2. `conductor_setup(bot_username)` → создать группу, добавить бота
  3. Для каждого аккаунта (все параллельно через asyncio.gather):
     - `conductor_join_group(account_id, invite_link)`
     - `start_bot(account_id, bot_username, ref_param)`
     - `wait_bot_response(account_id, bot_username, timeout=15)`
     - Если кнопки "Subscribe/Join" → `get_inline_button_urls` → `join_channel`
     - Если кнопка "Verify/Проверить" → `click_button`
     - sleep 60с (правило #4)
  4. `conductor_cleanup(group_id)`
  5. Отчёт: сколько засчитано, сколько ошибок

  **Ключевые правила:**
  - НИКОГДА не использовать один api_id для нескольких аккаунтов одновременно
  - FloodWait ≤ 600с — ждать и продолжить. >600с — пропустить аккаунт
  - InviteRequestSentError = УСПЕХ (approval-канал), продолжать
  