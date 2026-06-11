"""
react_loop.py — Основной ReAct цикл агента RefAgent.

Цикл: Think (LLM call) → Act (tool execution) → Observe (inject result) → повтор.

Поддерживает:
  - OpenRouter: нативный tool calling (ProviderResponse.tool_calls)
  - FavoriteAPI: парсинг <tool_call>{...}</tool_call> из текста
  - asyncio.Event для мгновенной остановки
  - Автоматическое сжатие / reset контекста FavoriteAPI
  - Harold pattern через conductor_tools
  - Поиск в библиотеке при ошибках
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Optional, Callable, Any, Awaitable

from providers.base import BaseProvider, Message, ProviderResponse
from providers.favoriteapi import FavoriteAPIProvider
from agent.tools_registry import TOOL_DEFS
from agent.system_prompt import build_system_prompt
from agent.context_manager import context_manager
from agent.state import agent_state
from config.constants import (
    TIMING_BETWEEN_REFERRALS, TIMING_BETWEEN_ACCOUNTS,
    FAVORITEAPI_CTX_WARN_KB,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════
# ТИПЫ
# ════════════════════════════════════════════════════

LogCallback = Callable[[str], Awaitable[None]]   # async fn для отправки статус-логов


# ════════════════════════════════════════════════════
# ПАРСИНГ TOOL_CALL ДЛЯ FAVORITEAPI
# ════════════════════════════════════════════════════

TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)


def parse_tool_calls_from_text(text: str) -> list[dict]:
    """
    Извлечь JSON tool_call блоки из текстового ответа (FavoriteAPI mode).
    Returns list of {name: str, arguments: dict}
    """
    results = []
    for m in TOOL_CALL_RE.finditer(text):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
            if "name" in data:
                results.append({
                    "name":      data["name"],
                    "arguments": data.get("arguments", {}),
                })
        except json.JSONDecodeError:
            log.warning(f"[ReAct] Не удалось распарсить tool_call: {raw[:100]}")
    return results


def strip_tool_calls(text: str) -> str:
    """Удалить <tool_call>...</tool_call> блоки из текста."""
    return TOOL_CALL_RE.sub("", text).strip()


# ════════════════════════════════════════════════════
# EXECUTOR — диспетчер инструментов
# ════════════════════════════════════════════════════

class ToolExecutor:
    """Выполняет вызовы инструментов агента."""

    async def execute(self, name: str, arguments: dict) -> str:
        """
        Выполнить инструмент по имени.
        Returns: строковый результат (для inject обратно в контекст LLM).
        """
        try:
            result = await self._dispatch(name, arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            log.exception(f"[Executor] Ошибка инструмента {name}: {e}")
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    async def _dispatch(self, name: str, args: dict) -> Any:
        # ── Telegram ──
        if name == "connect_account":
            from tools.tg_tools import connect_account
            return await connect_account(args["account_id"])

        if name == "disconnect_account":
            from tools.tg_tools import disconnect_account
            return await disconnect_account(args["account_id"])

        if name == "join_channel":
            from tools.tg_tools import join_channel
            return await join_channel(args["account_id"], args["link"])

        if name == "start_bot":
            from tools.tg_tools import start_bot
            return await start_bot(
                args["account_id"],
                args["bot_username"],
                args.get("start_param"),
            )

        if name == "send_message":
            from tools.tg_tools import send_message
            return await send_message(args["account_id"], args["peer"], args["text"])

        if name == "get_messages":
            from tools.tg_tools import get_messages
            return await get_messages(args["account_id"], args["peer"], args.get("limit", 5))

        if name == "click_button":
            from tools.tg_tools import click_button
            return await click_button(
                args["account_id"], args["peer"], args["message_id"],
                args.get("button_text"), args.get("row", 0), args.get("col", 0),
            )

        if name == "wait_bot_response":
            from tools.tg_tools import wait_bot_response
            return await wait_bot_response(
                args["account_id"], args["peer"], args.get("timeout", 10)
            )

        # ── Conductor ──
        if name == "conductor_setup":
            from tools.conductor_tools import conductor_setup
            return await conductor_setup(args["bot_username"])

        if name == "conductor_join_group":
            from tools.conductor_tools import conductor_join_group
            return await conductor_join_group(args["account_id"], args["invite_link"])

        if name == "conductor_cleanup":
            from tools.conductor_tools import conductor_cleanup
            return await conductor_cleanup(args["group_id"])

        # ── Library ──
        if name == "search_library":
            from tools.library_tools import search_library, format_search_results
            results = search_library(args["query"])
            return {"results": format_search_results(results)}

        if name == "write_library":
            from tools.library_tools import write_library
            return write_library(args["slug"], args["title"], args["content"])

        # ── Terminal ──
        if name == "execute_command":
            from tools.terminal_tools import execute_command, format_command_result
            result = await execute_command(args["command"], args.get("timeout", 30))
            return {"text": format_command_result(result), **result}

        if name == "run_temp_script":
            from tools.terminal_tools import run_temp_script, format_command_result
            result = await run_temp_script(args["code"], args.get("timeout", 60))
            return {"text": format_command_result(result), **result}

        # ── Plan ──
        if name == "propose_plan":
            from agent.plan_manager import plan_manager
            plan = await plan_manager.create(
                steps       = args["steps"],
                description = args.get("description", ""),
                ref_url     = args.get("ref_url", ""),
            )
            return {
                "ok":        True,
                "status":    "plan_proposed",
                "plan_text": plan.format_text(),
                "steps":     args["steps"],
            }

        return {"ok": False, "error": f"Неизвестный инструмент: {name}"}


# ════════════════════════════════════════════════════
# REACT LOOP
# ════════════════════════════════════════════════════

class ReactLoop:
    """
    Основной ReAct цикл.

    Использование:
        loop = ReactLoop(provider)
        await loop.run(chat_id, user_message, log_callback)
    """

    MAX_ITERATIONS = 50
    MAX_NO_TOOL    = 3   # сколько раз подряд LLM не вызвала инструмент

    def __init__(
        self,
        provider:    BaseProvider,
        stop_event:  Optional[asyncio.Event] = None,
        log_cb:      Optional[LogCallback]   = None,
    ):
        self._provider    = provider
        self._stop_event  = stop_event or asyncio.Event()
        self._log_cb      = log_cb
        self._executor    = ToolExecutor()
        self._history:    list[Message] = []
        self._is_favoriteapi = isinstance(provider, FavoriteAPIProvider)

    @property
    def stop_event(self) -> asyncio.Event:
        return self._stop_event

    def stop(self) -> None:
        self._stop_event.set()

    async def run(
        self,
        chat_id:      int,
        user_message: str,
        plan_steps:   Optional[list[str]] = None,
    ) -> str:
        """
        Запустить ReAct цикл.
        Возвращает итоговый текстовый ответ агента.
        """
        agent_state.set_active(True, chat_id)
        self._stop_event.clear()

        try:
            return await self._react_loop(user_message, plan_steps)
        finally:
            agent_state.set_active(False)
            from tools.tg_tools import disconnect_all
            await disconnect_all()

    async def _react_loop(
        self,
        user_message: str,
        plan_steps:   Optional[list[str]],
    ) -> str:
        # Собрать системный промпт
        sys_prompt = build_system_prompt(
            provider   = "favoriteapi" if self._is_favoriteapi else "openrouter",
            plan_steps = plan_steps,
        )

        # Инициализировать историю
        self._history = [
            Message(role="system",  content=sys_prompt),
            Message(role="user",    content=user_message),
        ]

        # Инструменты для OpenRouter
        tools = None if self._is_favoriteapi else _get_openrouter_tools()

        no_tool_streak = 0
        last_text      = ""

        for iteration in range(self.MAX_ITERATIONS):
            # Проверить стоп
            if self._stop_event.is_set():
                await self._log("🛑 Остановлено пользователем")
                return "Задача остановлена пользователем."

            # ── FavoriteAPI: проверить контекст ───────────────────────────
            if self._is_favoriteapi:
                await context_manager.maybe_reset(self._provider)
                if context_manager.at_limit:
                    await self._log("⚠️ Контекст заполнен — reset")
                    self._history = self._history[:2]   # system + user

            # ── LLM вызов ────────────────────────────────────────────────
            await self._log(f"🤔 Думаю... (итерация {iteration + 1})")
            try:
                response: ProviderResponse = await self._provider.chat(
                    messages = self._history,
                    tools    = tools,
                )
            except Exception as e:
                await self._log(f"❌ Ошибка провайдера: {e}")
                await asyncio.sleep(2)
                continue

            # Обновить контекст FavoriteAPI
            if self._is_favoriteapi and response.context_kb is not None:
                context_manager.update(response.context_kb)

            # ── Обработать ответ ─────────────────────────────────────────
            tool_calls_to_execute: list[dict] = []

            if response.has_tool_calls:
                # OpenRouter: нативные tool calls
                for tc in response.tool_calls:
                    tool_calls_to_execute.append({
                        "id":        tc.id,
                        "name":      tc.name,
                        "arguments": tc.arguments,
                    })
                self._history.append(Message(role="assistant", content=response.text or ""))

            elif response.text:
                # FavoriteAPI или text-режим: парсить <tool_call>
                parsed = parse_tool_calls_from_text(response.text)
                if parsed:
                    tool_calls_to_execute = [{"id": f"tc_{i}", **p} for i, p in enumerate(parsed)]
                    clean_text = strip_tool_calls(response.text)
                    self._history.append(Message(role="assistant", content=response.text))
                    if clean_text:
                        await self._log(f"💭 {clean_text[:200]}")
                else:
                    # Чисто текстовый ответ — нет вызова инструментов
                    last_text = response.text
                    self._history.append(Message(role="assistant", content=response.text))
                    no_tool_streak += 1

                    # Если propose_plan в тексте — скорее всего агент завершил
                    if no_tool_streak >= self.MAX_NO_TOOL or self._looks_final(response.text):
                        await self._log(f"✅ Агент завершил работу")
                        return last_text
                    continue

            # ── Выполнить инструменты ─────────────────────────────────────
            if tool_calls_to_execute:
                no_tool_streak = 0
                for tc in tool_calls_to_execute:
                    if self._stop_event.is_set():
                        break
                    await self._log(f"🔧 {tc['name']}({_args_preview(tc['arguments'])})")
                    obs = await self._executor.execute(tc["name"], tc["arguments"])

                    # Inject результат обратно в историю
                    if response.has_tool_calls:
                        # OpenRouter: tool result message
                        self._history.append(Message(
                            role    = "tool",
                            content = json.dumps({
                                "tool_call_id": tc["id"],
                                "content":      obs,
                            }),
                        ))
                    else:
                        # FavoriteAPI: user message с результатом
                        self._history.append(Message(
                            role    = "user",
                            content = f"[Результат {tc['name']}]: {obs}",
                        ))

                    await self._log(f"📋 {tc['name']} → {obs[:100]}")

                    # Спец обработка propose_plan — ждать подтверждения пользователя
                    if tc["name"] == "propose_plan":
                        return f"__plan_proposed__{obs}"

        return last_text or "Агент завершил работу (достигнут лимит итераций)."

    async def _log(self, text: str) -> None:
        log.info(f"[ReAct] {text}")
        if self._log_cb:
            try:
                await self._log_cb(text)
            except Exception:
                pass

    @staticmethod
    def _looks_final(text: str) -> bool:
        """Эвристика: текст выглядит как финальный ответ."""
        markers = ["задача выполнена", "задача завершена", "готово", "завершено",
                   "рефераллы засчитаны", "работа завершена", "отчёт"]
        lower   = text.lower()
        return any(m in lower for m in markers)


# ════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════

def _get_openrouter_tools() -> list[dict]:
    from agent.tools_registry import get_openrouter_tools
    return get_openrouter_tools()


def _args_preview(args: dict, max_len: int = 60) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s[:max_len] + "..." if len(s) > max_len else s
