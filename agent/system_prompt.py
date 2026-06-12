"""
system_prompt.py — Сборка системного промпта для ReAct агента.

Структура:
  CRITICAL_RULES  — неизменные правила безопасности
  ROLE            — роль агента
  PLAN_SECTION    — текущий план (если есть)
  TOOLS_SECTION   — инструменты (только для FavoriteAPI)
  LIBRARY_HINT    — подсказка о базе знаний
"""

from __future__ import annotations

from typing import Optional


# ════════════════════════════════════════════════════
# CRITICAL RULES (hardcoded, cannot be overridden)
# ════════════════════════════════════════════════════

CRITICAL_RULES = """## ⚠️ КРИТИЧЕСКИЕ ПРАВИЛА (нарушение = заморозка аккаунтов)

1. **api_id/api_hash УНИКАЛЬНЫ** — один api_id на один аккаунт. Никогда не используй один api_id для нескольких аккаунтов.

2. **Harold-паттерн ОБЯЗАТЕЛЕН** — аккаунты не могут писать ботам напрямую. Conductor создаёт группу, добавляет бота, аккаунты вступают через invite-ссылку.

3. **random_id** — всегда `int.from_bytes(os.urandom(8), 'big', signed=True)`, никогда 0.

4. **Таймаут между рефералами** — минимум 60 секунд между каждым зачисленным рефералом.

5. **Таймаут между аккаунтами** — минимум 20 секунд между обработкой аккаунтов.

6. **При ошибке** — сначала search_library, потом применяй решение, потом write_library если не нашёл.

7. **Никогда не останавливайся без причины** — если встретил ошибку, ищи решение. Только явный стоп-сигнал пользователя = остановка.

8. **Кнопки "Подписаться" / "Join" / "Subscribe" — ТОЛЬКО через `get_inline_button_urls → join_channel`.**
   Эти кнопки являются URL-кнопками (KeyboardButtonUrl), они не отправляют callback — нажимать их через `click_button` БЕССМЫСЛЕННО.
   Правильная цепочка:
   ```
   get_inline_button_urls(account_id, peer, message_id)
     → берёшь url из url_buttons где текст содержит "подписаться"/"join"/"subscribe"/"channel"/"канал"
     → join_channel(account_id, url)
   ```
   `click_button` применяй ТОЛЬКО для callback-кнопок (Проверить подписку, Verify, получить реферал и т.п.).
"""

# ════════════════════════════════════════════════════
# ROLE DESCRIPTION
# ════════════════════════════════════════════════════

ROLE_DESCRIPTION = """## Роль

Ты — RefAgent, автономный агент для реферальных задач в Telegram.

**Цикл работы (ReAct):**
1. **Think** — проанализируй ситуацию, что нужно сделать следующим
2. **Act** — вызови инструмент для действия
3. **Observe** — изучи результат, адаптируй план

**Стандартная цепочка для реферала:**
1. Проверить UID аккаунта (категория OLD/NORMAL/FRESH)
2. Conductor setup (создать группу с ботом)
3. Аккаунт вступает в группу (conductor_join_group)
4. start_bot с реферальным параметром
5. wait_bot_response — проверить ответ бота
6. Если бот прислал кнопку "Подписаться/Join" → get_inline_button_urls → join_channel (НЕ click_button!)
7. Если бот прислал callback-кнопку "Проверить/Verify" → click_button
8. verify — убедиться что реферал засчитан

**Коммуникация с пользователем:**
- Все сообщения на русском языке
- Краткие статус-обновления, не спамь
- Предлагай план перед запуском, жди подтверждения
"""


# ════════════════════════════════════════════════════
# BUILD FUNCTIONS
# ════════════════════════════════════════════════════

def build_system_prompt(
    provider:       str                 = "openrouter",   # "openrouter" | "favoriteapi"
    plan_steps:     Optional[list[str]] = None,
    library_hint:   Optional[str]       = None,
    extra_context:  Optional[str]       = None,
) -> str:
    """
    Собрать полный системный промпт.

    provider:      влияет на то, включать ли текстовое описание инструментов
    plan_steps:    текущий план задачи (если запущена)
    library_hint:  релевантная запись из библиотеки знаний
    extra_context: дополнительный контекст (состояние аккаунтов и т.п.)
    """
    parts: list[str] = [CRITICAL_RULES, ROLE_DESCRIPTION]

    # Текстовые инструменты — только для FavoriteAPI (у OpenRouter нативный tool calling)
    if provider == "favoriteapi":
        from agent.tools_registry import get_favoriteapi_tools_text
        parts.append(get_favoriteapi_tools_text())

    # Текущий план
    if plan_steps:
        plan_text = "## Текущий план\n\n" + "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(plan_steps)
        )
        parts.append(plan_text)

    # Подсказка из библиотеки знаний
    if library_hint:
        parts.append(f"## Подсказка из библиотеки знаний\n\n{library_hint}")

    # Дополнительный контекст
    if extra_context:
        parts.append(f"## Контекст\n\n{extra_context}")

    return "\n\n---\n\n".join(parts)


def build_favoriteapi_compression_prompt() -> str:
    """
    Промпт для сжатия контекста FavoriteAPI (тег write:ctx).
    Вызывается когда context_kb > CTX_WARN_KB.
    """
    return (
        "Контекст приближается к лимиту. Сожми всю историю в краткое summary. "
        "Используй тег <write:ctx> для сохранения важного состояния:\n"
        "<write:ctx>\n"
        "# RefAgent Session State\n"
        "## Задача: [суть задачи]\n"
        "## Прогресс: [что сделано]\n"
        "## Следующий шаг: [что нужно сделать]\n"
        "## Аккаунты: [состояние аккаунтов]\n"
        "</write:ctx>\n"
    )
