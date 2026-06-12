"""
tools_registry.py — Реестр всех инструментов агента с JSON-схемами.

Для OpenRouter: возвращает OpenAI-format tool definitions (нативный tool_use).
Для FavoriteAPI: возвращает текстовое описание инструментов для системного промпта.
"""

from __future__ import annotations

from tools.skills_db import (
    search_skills as _search_skills_fn,
    get_skill as _get_skill_fn,
    parse_workflow_steps,
    increment_used as _increment_skill_used,
)

from typing import Any


# ════════════════════════════════════════════════════
# RAW TOOL DEFINITIONS
# ════════════════════════════════════════════════════

TOOL_DEFS: list[dict[str, Any]] = [

    # ── Telegram: подключение и аккаунты ──────────────────────────────
    {
        "name": "connect_account",
        "description": "Подключить Telegram-аккаунт по его ID из базы. Проверяет авторизацию и возвращает uid, phone, категорию UID.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "ID аккаунта в базе данных"},
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "disconnect_account",
        "description": "Отключить Telegram-аккаунт. Вызывать после завершения работы с аккаунтом.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer"},
            },
            "required": ["account_id"],
        },
    },

    # ── Telegram: вступление в каналы/группы ────────────────────────────
    {
        "name": "join_channel",
        "description": "Вступить в Telegram канал или группу по ссылке или username.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer"},
                "link":       {"type": "string", "description": "Username (@channel) или invite-ссылка (t.me/+HASH или t.me/joinchat/HASH)"},
            },
            "required": ["account_id", "link"],
        },
    },

    # ── Telegram: работа с ботами ───────────────────────────────────────
    {
        "name": "start_bot",
        "description": "Отправить команду /start боту (опционально с deeplink параметром). Harold: бот должен быть в общей группе.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id":   {"type": "integer"},
                "bot_username": {"type": "string", "description": "Username бота без @"},
                "start_param":  {"type": "string", "description": "Deeplink параметр (часть после /start в реф-ссылке)"},
            },
            "required": ["account_id", "bot_username"],
        },
    },
    {
        "name": "send_message",
        "description": "Отправить текстовое сообщение боту или пользователю.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id":   {"type": "integer"},
                "peer":         {"type": "string", "description": "Username или числовой ID получателя"},
                "text":         {"type": "string"},
            },
            "required": ["account_id", "peer", "text"],
        },
    },
    {
        "name": "get_messages",
        "description": "Получить последние сообщения из диалога с ботом/пользователем.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id":   {"type": "integer"},
                "peer":         {"type": "string"},
                "limit":        {"type": "integer", "default": 5},
            },
            "required": ["account_id", "peer"],
        },
    },
    {
        "name": "click_button",
        "description": "Нажать inline-кнопку в сообщении бота. Нужен message_id и текст кнопки или её позиция.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id":   {"type": "integer"},
                "peer":         {"type": "string"},
                "message_id":   {"type": "integer"},
                "button_text":  {"type": "string", "description": "Текст кнопки (приоритет)"},
                "row":          {"type": "integer", "default": 0},
                "col":          {"type": "integer", "default": 0},
            },
            "required": ["account_id", "peer", "message_id"],
        },
    },
    {
        "name": "wait_bot_response",
        "description": "Ждать ответ бота после действия. Возвращает список новых сообщений.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id":   {"type": "integer"},
                "peer":         {"type": "string"},
                "timeout":      {"type": "integer", "default": 10, "description": "Максимальное ожидание в секундах"},
            },
            "required": ["account_id", "peer"],
        },
    },

    # ── Harold Conductor ────────────────────────────────────────────────
    {
        "name": "conductor_setup",
        "description": "Создать временную группу через проводника, добавить в неё целевого бота. Возвращает group_id и invite_link.",
        "parameters": {
            "type": "object",
            "properties": {
                "bot_username": {"type": "string", "description": "Username целевого бота"},
            },
            "required": ["bot_username"],
        },
    },
    {
        "name": "conductor_join_group",
        "description": "Аккаунт вступает в группу проводника по invite-ссылке (Harold pattern).",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id":   {"type": "integer"},
                "invite_link":  {"type": "string"},
            },
            "required": ["account_id", "invite_link"],
        },
    },
    {
        "name": "conductor_cleanup",
        "description": "Удалить временную группу проводника после завершения задачи.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_id": {"type": "integer"},
            },
            "required": ["group_id"],
        },
    },

    # ── Библиотека знаний ───────────────────────────────────────────────
    {
        "name": "search_library",
        "description": "Поиск по базе знаний об ошибках Telegram и решениях. Используй при любой ошибке.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Описание ошибки или ключевое слово"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "write_library",
        "description": "Записать новую запись в библиотеку знаний. Используй после успешного решения нестандартной ошибки.",
        "parameters": {
            "type": "object",
            "properties": {
                "slug":    {"type": "string", "description": "Короткий идентификатор (snake_case, латиница)"},
                "title":   {"type": "string"},
                "content": {"type": "string", "description": "Markdown-текст с описанием ошибки и решения"},
            },
            "required": ["slug", "title", "content"],
        },
    },

    # ── Утилиты ─────────────────────────────────────────────────────────
    {
        "name": "sleep_seconds",
        "description": "Подождать N секунд. Используй вместо run_temp_script(time.sleep(n)).",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "integer", "description": "Количество секунд ожидания"},
            },
            "required": ["seconds"],
        },
    },
    {
        "name": "get_inline_button_urls",
        "description": (
            "Вернуть URL-кнопки из сообщения бота (тип KeyboardButtonUrl). "
            "Используй чтобы получить ссылки на каналы для подписки — "
            "затем вызывай join_channel для каждого url из url_buttons."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer"},
                "peer":       {"type": "string", "description": "Username бота"},
                "message_id": {"type": "integer"},
            },
            "required": ["account_id", "peer", "message_id"],
        },
    },

    # ── Терминал ────────────────────────────────────────────────────────
    {
        "name": "execute_command",
        "description": "Выполнить shell-команду. Только для диагностики и утилит.",
        "parameters": {
            "type": "object",
            "properties": {
                "command":  {"type": "string"},
                "timeout":  {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "run_temp_script",
        "description": "Написать и запустить временный Python-скрипт. Возвращает stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "code":     {"type": "string", "description": "Python-код для выполнения"},
                "timeout":  {"type": "integer", "default": 60},
            },
            "required": ["code"],
        },
    },

    # ── Инструменты аккаунтов ────────────────────────────────────────────
    {
        "name": "list_accounts",
        "description": (
            "Вернуть список аккаунтов из базы. "
            "Используй в начале задачи чтобы проверить, есть ли уже загруженные аккаунты "
            "перед вызовом load_sessions. Опционально фильтр по status (ACTIVE/FROZEN/BANNED)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Фильтр по статусу: ACTIVE | FROZEN | BANNED | UNKNOWN. Пусто = все."},
            },
            "required": [],
        },
    },

    # ── Загрузка сессий ──────────────────────────────────────────────────
    {
        "name": "load_sessions",
        "description": (
            "Загрузить все .session + .json файлы из папки uploads в базу аккаунтов. "
            "Вызывай если пользователь прикрепил файлы сессий перед задачей. "
            "Возвращает сколько загружено, сколько ошибок и список результатов."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },

    # ── Управление планом ────────────────────────────────────────────────
    {
        "name": "propose_plan",
        "description": "Предложить план задачи пользователю. Агент вызывает это когда собрал достаточно информации.",
        "parameters": {
            "type": "object",
            "properties": {
                "steps":       {"type": "array", "items": {"type": "string"}, "description": "Список шагов"},
                "ref_url":     {"type": "string", "description": "Реферальная ссылка"},
                "description": {"type": "string", "description": "Краткое описание задачи"},
            },
            "required": ["steps", "description"],
        },
    },
      # ── Skills ───────────────────────────────────────────────────────────────
      {
          "name": "search_skills",
          "description": (
              "Искать навыки агента по теме. Навыки = инструкции/алгоритмы которые "
              "пользователь добавил для специфичных задач (боты, сценарии, обходы). "
              "Вызывай в начале задачи если не уверен в алгоритме. "
              "query: строка поиска, например 'ref cryptobot' или 'flood bypass'."
          ),
          "parameters": {
              "type": "object",
              "properties": {
                  "query": {"type": "string", "description": "Тема поиска: название бота, тип задачи, ошибка"},
              },
              "required": ["query"],
          },
      },
      {
          "name": "use_skill",
          "description": (
              "Загрузить workflow-навык и получить готовый план шагов для propose_plan. "
              "Используй когда search_skills нашёл подходящий workflow-навык."
          ),
          "parameters": {
              "type": "object",
              "properties": {
                  "name": {"type": "string", "description": "Slug навыка (например: warmup_accounts)"},
              },
              "required": ["name"],
          },
      },
            parameters  = {
              "type": "object",
              "properties": {
                  "name": {"type": "string", "description": "Slug навыка (например: warmup_accounts)"},
              },
              "required": ["name"],
          },
      ),
]


# ════════════════════════════════════════════════════
# OPENROUTER FORMAT (native tool calling)
# ════════════════════════════════════════════════════

def get_openrouter_tools() -> list[dict]:
    """Вернуть список инструментов в формате OpenAI (для OpenRouter)."""
    return [
        {
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t["description"],
                "parameters":  t["parameters"],
            },
        }
        for t in TOOL_DEFS
    ]


# ════════════════════════════════════════════════════
# FAVORITEAPI FORMAT (text in system prompt)
# ════════════════════════════════════════════════════

def get_favoriteapi_tools_text() -> str:
    """
    Вернуть текстовое описание всех инструментов для системного промпта FavoriteAPI.
    LLM должна отвечать в формате:
        <tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>
    """
    lines = ["## Доступные инструменты\n"]
    for t in TOOL_DEFS:
        props = t["parameters"].get("properties", {})
        required = t["parameters"].get("required", [])
        params_str = ", ".join(
            f"{k}{'*' if k in required else '?'}: {v.get('type', 'any')}"
            for k, v in props.items()
        )
        lines.append(f"### {t['name']}({params_str})")
        lines.append(t["description"])
        lines.append("")
    lines.append("Для вызова инструмента используй СТРОГО этот формат (только один вызов за ответ):")
    lines.append('`<tool_call>{"name": "tool_name", "arguments": {...}}</tool_call>`')
    return "\n".join(lines)


# ════════════════════════════════════════════════════
# LOOKUP
# ════════════════════════════════════════════════════

_TOOL_BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOL_DEFS}


def get_tool(name: str) -> dict | None:
    return _TOOL_BY_NAME.get(name)


def list_tool_names() -> list[str]:
    return list(_TOOL_BY_NAME.keys())
