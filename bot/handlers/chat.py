"""
chat.py — Обработчики чата с агентом.

FSM состояния:
  dialog       — свободный диалог, ждём задачу
  awaiting_run — план показан, ждём [Запустить]
  running      — агент выполняет задачу
  stopped      — задача остановлена

Каждый чат имеет собственный API ключ (active_chat_id в FSM data).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.main_menu import (
    CB_STOP, CB_STOP_WRITE,
    CB_PLAN_RUN, CB_PLAN_EDIT, CB_PLAN_CANCEL,
    plan_confirm_keyboard, task_controls_keyboard, back_to_main_keyboard,
)
from bot.keyboards.reply_keyboard import (
    idle_keyboard, running_keyboard, plan_keyboard,
)
from bot.ui.animator import Animator
from bot.ui.status_blocks import send_log, send_error
from bot.file_buffer import pop_files, has_files
from agent.react_loop import ReactLoop
from agent.plan_manager import plan_manager
from agent.state import agent_state
from providers import build_provider_from_chat

log = logging.getLogger(__name__)

router  = Router()
_animator: Optional[Animator] = None
_loop:     Optional[ReactLoop] = None
_task:     Optional[asyncio.Task] = None


def set_animator(a: Animator) -> None:
    global _animator
    _animator = a


def _get_loop():    return _loop
def _get_task():    return _task
def _stop_loop():
    if _loop:
        _loop.stop()


# ════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ════════════════════════════════════════════════════

class ChatStates(StatesGroup):
    dialog       = State()
    awaiting_run = State()
    running      = State()
    stopped      = State()


# ════════════════════════════════════════════════════
# HELPER — загрузить активный чат
# ════════════════════════════════════════════════════

async def _load_active_chat(state: FSMContext):
    """Вернуть ChatRecord активного чата или None."""
    from tools.chat_db import get_chat
    data = await state.get_data()
    chat_id = data.get("active_chat_id")
    if not chat_id:
        return None
    return await get_chat(chat_id)


async def _no_chat_reply(message: Message) -> None:
    """Показать подсказку когда чат не выбран."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.reply(
        "💬 <b>Чат не выбран</b>\n\n"
        "Создай новый чат или открой существующий.\n"
        "Каждый чат использует свой API ключ.",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Новый чат",  callback_data="chat:new")],
            [InlineKeyboardButton(text="💬 Мои чаты",   callback_data="chat:list")],
        ]),
    )


# ════════════════════════════════════════════════════
# СВОБОДНЫЙ ДИАЛОГ
# ════════════════════════════════════════════════════

@router.message(ChatStates.dialog)
async def handle_dialog_message(message: Message, state: FSMContext, bot: Bot) -> None:
    chat = await _load_active_chat(state)
    if not chat:
        await _no_chat_reply(message)
        return

    try:
        provider = build_provider_from_chat(chat)
    except ValueError as e:
        await message.reply(
            f"⚠️ Провайдер чата не настроен: {e}\n\n"
            "Удали чат и создай новый с корректным API ключом.",
            parse_mode   = "HTML",
            reply_markup = idle_keyboard(),
        )
        return

    tg_chat_id = message.chat.id   # Telegram chat_id — только для аниматора

    # Собрать прикреплённые файлы из sandbox этого чата (ключ = chat.id, не Telegram chat_id)
    pending = pop_files(chat.id)
    user_text = message.text or ""
    if pending:
        attachment_lines = "\n".join(f.context_line() for f in pending)
        user_text = f"{user_text}\n\n{attachment_lines}" if user_text else attachment_lines

    anim = {"msg_id": None}
    if _animator:
        anim["msg_id"] = await _animator.start(tg_chat_id, "thinking")

    from agent.status_event import StatusEvent
    from agent.status_event import KIND_THOUGHT as _KIND_THOUGHT

    async def _dialog_log_cb(event: StatusEvent) -> None:
        if event.kind != _KIND_THOUGHT:
            return
        raw = event.data.get("text", "").strip()
        if not raw:
            return
        if _animator and anim["msg_id"]:
            await _animator.finalize(tg_chat_id, anim["msg_id"], f"💭 {raw[:500]}")
            anim["msg_id"] = None
        if _animator:
            anim["msg_id"] = await _animator.start(tg_chat_id, "thinking")

    try:
        react  = ReactLoop(provider=provider, log_cb=_dialog_log_cb, bot=bot)
        result = await react.run(
            chat_id      = tg_chat_id,
            user_message = user_text,
        )

        if result.startswith("__plan_proposed__"):
            plan_data = json.loads(result[len("__plan_proposed__"):] or "{}")
            plan_text = plan_data.get("plan_text", "")

            if _animator and anim["msg_id"]:
                await _animator.stop_only(anim["msg_id"])
                try:
                    await bot.delete_message(tg_chat_id, anim["msg_id"])
                except Exception:
                    pass
                anim["msg_id"] = None

            await state.set_state(ChatStates.awaiting_run)
            await message.answer(
                plan_text + "\n\n<i>Подтверди план для запуска.</i>",
                parse_mode   = "HTML",
                reply_markup = plan_keyboard(),
            )
            await message.answer(
                "🚀 Запустить план?",
                reply_markup = plan_confirm_keyboard(),
            )
        else:
            if _animator and anim["msg_id"]:
                await _animator.finalize(tg_chat_id, anim["msg_id"], result)
            else:
                await message.answer(result, parse_mode="HTML", reply_markup=idle_keyboard())

    except Exception as e:
        log.exception(f"[Chat] Ошибка диалога: {e}")
        if _animator and anim["msg_id"]:
            await _animator.finalize(tg_chat_id, anim["msg_id"], f"❌ Ошибка: {e}")
        else:
            await message.reply(f"❌ Ошибка: {e}", reply_markup=idle_keyboard())


# ════════════════════════════════════════════════════
# ПОДТВЕРЖДЕНИЕ ПЛАНА (inline кнопки)
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_PLAN_RUN)
async def cb_plan_run(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if agent_state.is_active:
        await query.answer("Агент уже работает", show_alert=True)
        return

    plan = plan_manager.plan
    if not plan:
        await query.answer("План не найден", show_alert=True)
        return

    chat = await _load_active_chat(state)
    if not chat:
        await query.answer("Чат не выбран", show_alert=True)
        return

    await state.set_state(ChatStates.running)
    chat_id = query.message.chat.id

    await query.message.edit_text(
        "🚀 <b>Задача запущена</b>\n\nСтатус обновляется...",
        parse_mode   = "HTML",
        reply_markup = task_controls_keyboard(),
    )
    await bot.send_message(chat_id, "⚙️ Агент работает...", reply_markup=running_keyboard())
    await query.answer()

    try:
        provider = build_provider_from_chat(chat)
    except ValueError as e:
        await send_error(bot, chat_id, f"Провайдер не настроен: {e}")
        await state.set_state(ChatStates.dialog)
        return

    await _start_agent_task(bot, chat_id, state, provider, plan)


@router.callback_query(F.data == CB_PLAN_EDIT)
async def cb_plan_edit(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChatStates.dialog)
    await query.message.edit_text(
        "✏️ <b>Редактирование плана</b>\n\n"
        "Напиши что хочешь изменить — агент пересоставит план.",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_PLAN_CANCEL)
async def cb_plan_cancel(query: CallbackQuery, state: FSMContext) -> None:
    await plan_manager.cancel()
    await state.set_state(ChatStates.dialog)
    await query.message.edit_text(
        "❌ Задача отменена.",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer("Отменено")


# ════════════════════════════════════════════════════
# УПРАВЛЕНИЕ ЗАДАЧЕЙ (inline кнопки)
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_STOP)
async def cb_stop(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    _stop_loop()
    if _task and not _task.done():
        _task.cancel()

    agent_state.set_active(False)
    await state.set_state(ChatStates.stopped)
    await query.message.edit_reply_markup(reply_markup=None)
    await bot.send_message(
        query.message.chat.id,
        "🛑 <b>Остановлено.</b>",
        parse_mode   = "HTML",
        reply_markup = idle_keyboard(),
    )
    await query.answer("Останавливаю...")


@router.callback_query(F.data == CB_STOP_WRITE)
async def cb_stop_write(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    _stop_loop()
    if _task and not _task.done():
        _task.cancel()

    agent_state.set_active(False)
    await state.set_state(ChatStates.dialog)
    await query.message.edit_reply_markup(reply_markup=None)
    await bot.send_message(
        query.message.chat.id,
        "🛑 Остановлено. Напиши новую задачу.",
        parse_mode   = "HTML",
        reply_markup = idle_keyboard(),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# СООБЩЕНИЯ ПОКА АГЕНТ РАБОТАЕТ
# ════════════════════════════════════════════════════

@router.message(ChatStates.running)
async def handle_running_message(message: Message) -> None:
    await message.reply(
        "⚙️ Агент сейчас работает.\nНажми <b>⛔ Остановить</b> чтобы прервать.",
        parse_mode   = "HTML",
        reply_markup = running_keyboard(),
    )


@router.message(ChatStates.stopped)
async def handle_stopped_message(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.set_state(ChatStates.dialog)
    await handle_dialog_message(message, state, bot)


# ════════════════════════════════════════════════════
# ФОНОВЫЙ ЗАПУСК АГЕНТА
# ════════════════════════════════════════════════════

async def _start_agent_task(
    bot:      Bot,
    chat_id:  int,
    state:    FSMContext,
    provider,
    plan,
) -> None:
    global _loop, _task

    from agent.status_event import (
        KIND_THINKING, KIND_THOUGHT, KIND_TOOL_CALL, KIND_TOOL_RESULT,
        KIND_STEP, KIND_WAIT, KIND_RETRY, KIND_WARN, KIND_ERROR,
        KIND_STOP, KIND_DONE, KIND_SEPARATOR, KIND_CONTEXT_RESET,
    )
    from bot.ui.status_blocks import (
        send_thought, send_tool_call, send_tool_result,
        send_step, send_wait, send_retry, send_warn, send_error,
        send_separator, send_ok, send_account,
    )
    from agent.status_event import StatusEvent

    run_anim = {"msg_id": None}

    async def log_cb(event: StatusEvent) -> None:
        k = event.kind
        d = event.data
        try:
            if k in (KIND_THINKING, KIND_TOOL_CALL, KIND_TOOL_RESULT, KIND_DONE):
                pass
            elif k == KIND_THOUGHT:
                if _animator and run_anim["msg_id"]:
                    await _animator.stop_only(run_anim["msg_id"])
                    try:
                        await bot.delete_message(chat_id, run_anim["msg_id"])
                    except Exception:
                        pass
                    run_anim["msg_id"] = None
                await send_thought(bot, chat_id, d.get("text", ""))
                if _animator:
                    run_anim["msg_id"] = await _animator.start(chat_id, "thinking")
            elif k == KIND_STEP:
                await send_step(bot, chat_id, d["n"], d["total"], d.get("desc", ""))
            elif k == KIND_WAIT:
                await send_wait(bot, chat_id, d.get("seconds", 0), d.get("reason", ""))
            elif k == KIND_RETRY:
                await send_retry(bot, chat_id, d.get("attempt", 1), d.get("reason", ""))
            elif k in (KIND_WARN, KIND_CONTEXT_RESET):
                text = d.get("text", "Context reset") if k == KIND_CONTEXT_RESET else d.get("text", "")
                await send_warn(bot, chat_id, text)
            elif k == KIND_ERROR:
                await send_error(bot, chat_id, d.get("text", "Unknown error"))
            elif k == KIND_STOP:
                await send_log(bot, chat_id, "Stopped.")
            elif k == KIND_SEPARATOR:
                await send_separator(bot, chat_id)
            elif k == "account":
                await send_account(bot, chat_id, d.get("phone", "?"), d.get("status", ""))
        except Exception:
            pass

    _loop = ReactLoop(provider=provider, log_cb=log_cb, bot=bot)

    plan_text_for_llm = "\n".join(
        f"{i+1}. {s.description}" for i, s in enumerate(plan.steps)
    )
    user_msg = (
        f"Выполни план:\n{plan_text_for_llm}\n\n"
        f"Реферальная ссылка: {plan.ref_url}\n"
        f"Задача: {plan.description}"
    )

    async def _run() -> None:
        if _animator:
            run_anim["msg_id"] = await _animator.start(chat_id, "thinking")
        try:
            result = await _loop.run(
                chat_id      = chat_id,
                user_message = user_msg,
                plan_steps   = [s.description for s in plan.steps],
            )
            if _animator and run_anim["msg_id"]:
                await _animator.stop_only(run_anim["msg_id"])
                try:
                    await bot.delete_message(chat_id, run_anim["msg_id"])
                except Exception:
                    pass
                run_anim["msg_id"] = None
            from bot.ui.report import send_final_report, save_task_result
            await send_final_report(bot, chat_id, result, plan)
            await save_task_result(plan, result)
        except asyncio.CancelledError:
            if _animator and run_anim["msg_id"]:
                await _animator.stop_only(run_anim["msg_id"])
                try:
                    await bot.delete_message(chat_id, run_anim["msg_id"])
                except Exception:
                    pass
        except Exception as e:
            if _animator and run_anim["msg_id"]:
                await _animator.stop_only(run_anim["msg_id"])
                try:
                    await bot.delete_message(chat_id, run_anim["msg_id"])
                except Exception:
                    pass
            log.exception(f"[Chat] Ошибка агента: {e}")
            await send_error(bot, chat_id, str(e))
        finally:
            agent_state.set_active(False)
            await state.set_state(ChatStates.dialog)
            try:
                await bot.send_message(
                    chat_id,
                    "✅ Задача завершена.",
                    reply_markup = idle_keyboard(),
                )
            except Exception:
                pass

    _task = asyncio.create_task(_run())
