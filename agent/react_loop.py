"""
react_loop.py — ReAct loop: Think → Act → Observe → repeat.

Emits typed StatusEvent objects instead of raw strings so the UI
layer can pick the right status_block for each action.
"""

from __future__ import annotations

from tools.skills_db import (
    search_skills as _skills_search,
    get_skill as _get_skill,
    parse_workflow_steps,
    get_active_knowledge_skills,
    format_skill_for_agent,
    increment_used as _inc_skill,
)

import asyncio
import json
import logging
import re
import time
from typing import Optional, Any

from providers.base import BaseProvider, Message, ProviderResponse
from providers.favoriteapi import FavoriteAPIProvider
from agent.tools_registry import TOOL_DEFS
from agent.system_prompt import build_system_prompt
from agent.context_manager import context_manager
from agent.state import agent_state
from agent.status_event import (
    StatusEvent, StatusCallback,
    KIND_THINKING, KIND_THOUGHT, KIND_TOOL_CALL, KIND_TOOL_RESULT,
    KIND_STEP, KIND_WAIT, KIND_RETRY, KIND_WARN, KIND_ERROR,
    KIND_STOP, KIND_DONE, KIND_SEPARATOR, KIND_CONTEXT_RESET,
)
from config.constants import (
    TIMING_BETWEEN_REFERRALS, TIMING_BETWEEN_ACCOUNTS,
    FAVORITEAPI_CTX_WARN_KB,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════
# ПАРСИНГ TOOL_CALL ДЛЯ FAVORITEAPI
# ════════════════════════════════════════════════════

TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)


def parse_tool_calls_from_text(text: str) -> list[dict]:
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
            log.warning(f"[ReAct] Bad tool_call JSON: {raw[:100]}")
    return results


def strip_tool_calls(text: str) -> str:
    return TOOL_CALL_RE.sub("", text).strip()


# ════════════════════════════════════════════════════
# EXECUTOR
# ════════════════════════════════════════════════════

class ToolExecutor:

    async def execute(self, name: str, arguments: dict) -> str:
        try:
            result = await self._dispatch(name, arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            log.exception(f"[Executor] Tool {name} error: {e}")
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    async def _dispatch(self, name: str, args: dict) -> Any:
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

        if name == "conductor_setup":
            from tools.conductor_tools import conductor_setup
            return await conductor_setup(args["bot_username"])

        if name == "conductor_join_group":
            from tools.conductor_tools import conductor_join_group
            return await conductor_join_group(args["account_id"], args["invite_link"])

        if name == "conductor_cleanup":
            from tools.conductor_tools import conductor_cleanup
            return await conductor_cleanup(args["group_id"])

        if name == "search_library":
            from tools.library_tools import search_library, format_search_results
            results = search_library(args["query"])
            return {"results": format_search_results(results)}

        if name == "write_library":
            from tools.library_tools import write_library
            return write_library(args["slug"], args["title"], args["content"])

        if name == "execute_command":
            from tools.terminal_tools import execute_command, format_command_result
            result = await execute_command(args["command"], args.get("timeout", 30))
            return {"text": format_command_result(result), **result}

        if name == "run_temp_script":
            from tools.terminal_tools import run_temp_script, format_command_result
            result = await run_temp_script(args["code"], args.get("timeout", 60))
            return {"text": format_command_result(result), **result}

        if name == "list_accounts":
            from tools.db import get_all_accounts
            accs = await get_all_accounts()
            status_filter = args.get("status", "").upper()
            if status_filter:
                accs = [a for a in accs if a.status == status_filter]
            items = [
                {
                    "id":       a.id,
                    "phone":    a.phone,
                    "status":   a.status,
                    "category": a.uid_category,
                    "conductor": a.is_conductor,
                }
                for a in accs
            ]
            return {
                "ok":      True,
                "total":   len(items),
                "accounts": items,
                "text":    f"Аккаунтов в базе: {len(items)}\n" + "\n".join(
                    f"  id={a['id']} {a['phone']} [{a['status']}]{' (conductor)' if a['conductor'] else ''}"
                    for a in items
                ),
            }

        if name == "sleep_seconds":
            await asyncio.sleep(args["seconds"])
            return {"ok": True, "slept": args["seconds"]}

        if name == "get_inline_button_urls":
            from tools.tg_tools import get_inline_button_urls
            return await get_inline_button_urls(
                args["account_id"], args["peer"], args["message_id"]
            )

        if name == "load_sessions":
            from pathlib import Path
            from config.constants import UPLOADS_DIR
            from tools.session_tools import load_session_file, extract_and_load_zip

            uploads = Path(UPLOADS_DIR)
            results = []

            # Load .zip archives first
            for zp in uploads.glob("*.zip"):
                zr = await extract_and_load_zip(zp)
                results.extend(zr)

            # Load loose .session files that have a matching .json sidecar
            for sp in uploads.glob("*.session"):
                jr = sp.with_suffix(".json")
                if jr.exists():
                    r = await load_session_file(sp)
                    results.append(r)

            ok_count      = sum(1 for r in results if r.ok and not (r.error or "").endswith("(skipped)"))
            skipped_count = sum(1 for r in results if r.ok and (r.error or "").endswith("(skipped)"))
            err_count     = sum(1 for r in results if not r.ok)
            details       = [
                f"{'⏭' if (r.ok and (r.error or '').endswith('(skipped)')) else ('✅' if r.ok else '❌')} "
                f"{r.phone or '?'}: {r.error or f'id={r.account_id}'}"
                for r in results
            ]
            return {
                "ok":       True,
                "loaded":   ok_count,
                "skipped":  skipped_count,
                "errors":   err_count,
                "total":    len(results),
                "details":  details,
                "text":     f"Загружено: {ok_count}, пропущено (уже в базе): {skipped_count}, ошибок: {err_count}\n" + "\n".join(details),
            }

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

        return {"ok": False, "error": f"Unknown tool: {name}"}


# ════════════════════════════════════════════════════
# REACT LOOP
# ════════════════════════════════════════════════════

class ReactLoop:

    MAX_ITERATIONS = 50
    MAX_NO_TOOL    = 3

    def __init__(
        self,
        provider:    BaseProvider,
        stop_event:  Optional[asyncio.Event] = None,
        log_cb:      Optional[StatusCallback] = None,
        bot=None,    # Optional[aiogram.Bot] — for live countdown UI
    ):
        self._provider       = provider
        self._stop_event     = stop_event or asyncio.Event()
        self._log_cb         = log_cb
        self._bot            = bot       # passed from chat.py for countdown
        self._chat_id:       Optional[int] = None
        self._executor       = ToolExecutor()
        self._history:       list[Message] = []
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
        self._chat_id = chat_id          # store for countdown
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
        sys_prompt = build_system_prompt(
            provider   = "favoriteapi" if self._is_favoriteapi else "openrouter",
            plan_steps = plan_steps,
        )
        self._history = [
            Message(role="system", content=sys_prompt),
            Message(role="user",   content=user_message),
        ]
        tools          = None if self._is_favoriteapi else _get_openrouter_tools()
        no_tool_streak = 0
        last_text      = ""

        for iteration in range(self.MAX_ITERATIONS):

            if self._stop_event.is_set():
                await self._emit(KIND_STOP)
                return "Stopped by user."

            # FavoriteAPI context management
            if self._is_favoriteapi:
                await context_manager.maybe_reset(self._provider)
                if context_manager.at_limit:
                    await self._emit(KIND_CONTEXT_RESET)
                    self._history = self._history[:2]

            # ── LLM call ──────────────────────────────────────────────────
            await self._emit(KIND_THINKING, iteration=iteration + 1)
            try:
                response: ProviderResponse = await self._provider.chat(
                    messages = self._history,
                    tools    = tools,
                )
            except Exception as e:
                await self._emit(KIND_ERROR, text=str(e))
                await asyncio.sleep(2)
                continue

            if self._is_favoriteapi and response.context_kb is not None:
                context_manager.update(response.context_kb)

            # ── Parse response ────────────────────────────────────────────
            tool_calls_to_execute: list[dict] = []

            if response.has_tool_calls:
                # If model wrote commentary alongside tool call — show it
                if response.text and response.text.strip():
                    await self._emit(KIND_THOUGHT, text=response.text.strip()[:400])

                for tc in response.tool_calls:
                    tool_calls_to_execute.append({
                        "id":        tc.id,
                        "name":      tc.name,
                        "arguments": tc.arguments,
                    })
                # Store assistant message WITH tool_calls array for providers that need it (b.ai)
                self._history.append(Message(
                    role       = "assistant",
                    content    = response.text or "",
                    tool_calls = [
                        {
                            "id":   tc.id,
                            "type": "function",
                            "function": {
                                "name":      tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                ))

            elif response.text:
                parsed = parse_tool_calls_from_text(response.text)
                if parsed:
                    tool_calls_to_execute = [{"id": f"tc_{i}", **p} for i, p in enumerate(parsed)]
                    clean_text = strip_tool_calls(response.text)
                    self._history.append(Message(role="assistant", content=response.text))
                    if clean_text:
                        await self._emit(KIND_THOUGHT, text=clean_text[:300])
                else:
                    last_text = response.text
                    self._history.append(Message(role="assistant", content=response.text))
                    no_tool_streak += 1
                    if no_tool_streak >= self.MAX_NO_TOOL or self._looks_final(response.text):
                        await self._emit(KIND_DONE, text=last_text)
                        return last_text
                    continue

            # ── Execute tools ─────────────────────────────────────────────
            if tool_calls_to_execute:
                no_tool_streak = 0
                for tc in tool_calls_to_execute:
                    if self._stop_event.is_set():
                        break

                    tool_name    = tc["name"]
                    args_preview = _args_preview(tc["arguments"])
                    await self._emit(KIND_TOOL_CALL, tool=tool_name, args_preview=args_preview)

                    # ── sleep_seconds: use live countdown when bot available ──
                    if tool_name == "sleep_seconds" and self._bot and self._chat_id:
                        secs   = int(tc["arguments"].get("seconds", 0))
                        reason = tc["arguments"].get("reason", "")
                        from bot.ui.status_blocks import sleep_with_countdown
                        await sleep_with_countdown(self._bot, self._chat_id, secs, reason)
                        obs = json.dumps({"ok": True, "slept": secs}, ensure_ascii=False)
                    else:
                        obs = await self._executor.execute(tool_name, tc["arguments"])

                    # Inject result back into history
                    if response.has_tool_calls:
                        self._history.append(Message(
                            role         = "tool",
                            content      = obs,
                            tool_call_id = tc["id"],
                        ))
                    else:
                        self._history.append(Message(
                            role    = "user",
                            content = f"[Result {tool_name}]: {obs}",
                        ))

                    result_preview = _result_preview(obs)
                    await self._emit(KIND_TOOL_RESULT, tool=tool_name, result_preview=result_preview)

                    # Special: propose_plan → pause for user confirmation

                    # ── Skills tools ──────────────────────────────────────────────────────
  
                    if tool_name == "search_skills":
  
                        query   = tool_args.get("query", "")
  
                        results = _skills_search(query, limit=4)
  
                        if not results:
  
                            tool_result = f"Навыки по теме '{query}' не найдены."
  
                        else:
  
                            parts = []
  
                            for s in results:
  
                                icon = "⚡" if s.skill_type == "workflow" else "📖"
  
                                parts.append(f"{icon} [{s.name}] {s.title}\n{s.content[:500]}")
  
                            tool_result = "\n\n---\n".join(parts)

  
                    elif tool_name == "use_skill":
  
                        skill_name = tool_args.get("name", "")
  
                        skill      = _get_skill(skill_name)
  
                        if not skill:
  
                            tool_result = f"Навык '{skill_name}' не найден."
  
                        elif skill.skill_type != "workflow":
  
                            tool_result = f"Навык '{skill_name}' — knowledge-тип, используй как инструкцию а не plan."
  
                        else:
  
                            steps = parse_workflow_steps(skill)
  
                            await _inc_skill(skill_name)
  
                            tool_result = (
  
                                f"Навык '{skill.title}' загружен. Используй шаги в propose_plan:\n"
  
                                + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
  
                            )

  
                    elif tool_name == "propose_plan":
                        return f"__plan_proposed__{obs}"

                    # Special: emit typed events for known tools
                    await self._emit_tool_specific(tool_name, tc["arguments"], obs)

        return last_text or "Agent finished (iteration limit reached)."

    # ════════════════════════════════════════════════════
    # EMIT HELPERS
    # ════════════════════════════════════════════════════

    async def _emit(self, kind: str, **data) -> None:
        event = StatusEvent(kind=kind, data=data)
        log.info(f"[ReAct] {kind} {data}")
        if self._log_cb:
            try:
                await self._log_cb(event)
            except Exception:
                pass

    async def _emit_tool_specific(self, tool: str, args: dict, obs_raw: str) -> None:
        """Emit additional semantic events based on known tool names."""
        try:
            obs = json.loads(obs_raw)
        except Exception:
            obs = {}

        # wait events from tg_tools — e.g. flood wait
        if tool in ("join_channel", "start_bot", "send_message") and not obs.get("ok"):
            err = obs.get("error", "")
            if "flood" in err.lower() or "wait" in err.lower():
                await self._emit(KIND_RETRY, attempt=1, reason=err[:80])

        # account connection
        if tool == "connect_account":
            phone = obs.get("phone", args.get("account_id", ""))
            status = "connected" if obs.get("ok") else f"failed — {obs.get('error','')[:60]}"
            await self._emit("account", phone=str(phone), status=status)

    # ════════════════════════════════════════════════════
    # STATIC HELPERS
    # ════════════════════════════════════════════════════

    @staticmethod
    def _looks_final(text: str) -> bool:
        markers = [
            "task complete", "task done", "finished", "completed",
            "задача выполнена", "задача завершена", "готово", "завершено",
            "рефераллы засчитаны", "работа завершена", "отчёт",
        ]
        lower = text.lower()
        return any(m in lower for m in markers)


# ════════════════════════════════════════════════════
# MODULE HELPERS
# ════════════════════════════════════════════════════

def _get_openrouter_tools() -> list[dict]:
    from agent.tools_registry import get_openrouter_tools
    return get_openrouter_tools()


def _args_preview(args: dict, max_len: int = 80) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s[:max_len] + "..." if len(s) > max_len else s


def _result_preview(obs: str, max_len: int = 120) -> str:
    try:
        d = json.loads(obs)
        # Show ok status + first meaningful field
        parts = []
        if "ok" in d:
            parts.append(f"ok={d['ok']}")
        for key in ("error", "phone", "status", "text", "results"):
            if key in d:
                val = str(d[key])
                parts.append(f"{key}={val[:60]}")
                break
        return "  ".join(parts) if parts else obs[:max_len]
    except Exception:
        return obs[:max_len]
