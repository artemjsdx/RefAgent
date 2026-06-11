"""
chat.py — Обработчики чата с агентом RefAgent.

Режимы:
  DIALOG   — свободный диалог, агент собирает информацию о задаче
  PLAN     — показ плана пользователю [Запустить / Изменить / Отмена]
  RUNNING  — агент выполняет задачу (кнопки Остановить / Стоп+написать)
  STOPPED  — задача остановлена

Для FSM используется MemoryStorage из Dispatcher.
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
    CB_CHAT, CB_BACK_MAIN,
    CB_STOP, CB_STOP_WRITE,
    CB_PLAN_RUN, CB_PLAN_EDIT, CB_PLAN_CANCEL,
    plan_confirm_keyboard, task_controls_keyboard, back_to_main_keyboard,
)
from bot.ui.animator import Animator
from bot.ui.status_blocks import send_log, send_error
from agent.react_loop import ReactLoop
from agent.plan_manager import plan_manager
from agent.state import agent_state
from config.settings import get_settings
from providers import build_provider

log = logging.getLogger(__name__)

router  = Router()
_animator: Optional[Animator] = None
_loop:     Optional[ReactLoop] = None
_task:     Optional[asyncio.Task] = None


def set_animator(a: Animator) -> None:
    global _animator
    _animator = a


# ════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ════════════════════════════════════════════════════

class ChatStates(StatesGroup):
    dialog       = State()   # свободный диалог
    awaiting_run = State()   # план показан, ждём [Запустить]
    running      = State()   # агент работает
    stopped      = State()   # задача остановлена, ждём следующего


# ════════════════════════════════════════════════════
# ВХОД В ЧАТ
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_CHAT)
async def cb_open_chat(query: CallbackQuery, state: FSMContext) -> None:
    if agent_state.is_active:
        await query.message.edit_text(
            "<b>Агент работает</b>\n\n"
            "Задача сейчас выполняется. Используй кнопки управления.",
            parse_mode   = "HTML",
            reply_markup = task_controls_keyboard(),
        )
        await query.answer()
        return

    await state.set_state(ChatStates.dialog)
    await query.message.edit_text(
        "<b>Чат с агентом</b>\n\n"
        "Напиши задачу. Например:\n"
        "<i>Нужно зарефериться по ссылке t.me/somebot?start=abc123\n"
        "Жмём кнопку «Получить бонус» после старта.\n"
        "Есть 5 аккаунтов.</i>\n\n"
        "Агент уточнит детали и предложит план.",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# СВОБОДНЫЙ ДИАЛОГ (DIALOG STATE)
# ════════════════════════════════════════════════════

@router.message(ChatStates.dialog)
async def handle_dialog_message(message: Message, state: FSMContext, bot: Bot) -> None:
    """Пользователь пишет задачу — запускаем одну итерацию диалогового агента."""
    settings = get_settings()
    try:
        provider = build_provider(settings)
    except ValueError as e:
        await message.reply(
            f"⚠️ Провайдер не настроен: {e}\n\n"
            "Перейди в <b>Настройки → LLM Провайдер</b> и укажи API ключ.",
            parse_mode="HTML",
        )
        return

    anim_msg_id = None
    chat_id     = message.chat.id

    if _animator:
        anim_msg_id = await _animator.start(chat_id, "thinking")

    try:
        react = ReactLoop(provider=provider)

        # Запустить одну итерацию для ответа
        result = await react.run(
            chat_id      = chat_id,
            user_message = message.text or "",
        )

        # Если агент предложил план — переключить режим
        if result.startswith("__plan_proposed__"):
            plan_data_str = result[len("__plan_proposed__"):]
            plan_data     = json.loads(plan_data_str) if plan_data_str else {}
            plan_text     = plan_data.get("plan_text", "")

            if anim_msg_id:
                await _animator.stop_only(anim_msg_id)
                await bot.delete_message(chat_id, anim_msg_id)

            await state.set_state(ChatStates.awaiting_run)
            await message.answer(
                plan_text + "\n\n<i>Подтверди план для запуска.</i>",
                parse_mode   = "HTML",
                reply_markup = plan_confirm_keyboard(),
            )
        else:
            if _animator and anim_msg_id:
                await _animator.finalize(chat_id, anim_msg_id, result)
            else:
                await message.answer(result, parse_mode="HTML")

    except Exception as e:
        log.exception(f"[Chat] Ошибка диалога: {e}")
        if _animator and anim_msg_id:
            await _animator.finalize(chat_id, anim_msg_id, f"❌ Ошибка: {e}")
        else:
            await message.reply(f"❌ Ошибка: {e}")


# ════════════════════════════════════════════════════
# ПОДТВЕРЖДЕНИЕ ПЛАНА
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_PLAN_RUN)
async def cb_plan_run(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Пользователь нажал [Запустить] — запустить агента с планом."""
    if agent_state.is_active:
        await query.answer("Агент уже работает", show_alert=True)
        return

    plan = plan_manager.plan
    if not plan:
        await query.answer("План не найден", show_alert=True)
        return

    await state.set_state(ChatStates.running)
    chat_id = query.message.chat.id

    await query.message.edit_text(
        "🚀 <b>Задача запущена</b>\n\nСтатус будет обновляться...",
        parse_mode   = "HTML",
        reply_markup = task_controls_keyboard(),
    )
    await query.answer()

    # Запустить в фоне
    settings = get_settings()
    try:
        provider = build_provider(settings)
    except ValueError as e:
        await send_error(bot, chat_id, f"Провайдер не настроен: {e}")
        await state.set_state(ChatStates.dialog)
        return

    await _start_agent_task(bot, chat_id, state, provider, plan)


@router.callback_query(F.data == CB_PLAN_EDIT)
async def cb_plan_edit(query: CallbackQuery, state: FSMContext) -> None:
    """Пользователь хочет изменить план — вернуться в диалог."""
    await state.set_state(ChatStates.dialog)
    await query.message.edit_text(
        "<b>Редактирование плана</b>\n\n"
        "Напиши что хочешь изменить — агент пересоставит план.",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_PLAN_CANCEL)
async def cb_plan_cancel(query: CallbackQuery, state: FSMContext) -> None:
    """Отмена плана."""
    await plan_manager.cancel()
    await state.set_state(ChatStates.dialog)
    await query.message.edit_text(
        "Задача отменена. Напиши новую задачу когда будешь готов.",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer("Отменено")


# ════════════════════════════════════════════════════
# УПРАВЛЕНИЕ ЗАДАЧЕЙ (RUNNING STATE)
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_STOP)
async def cb_stop(query: CallbackQuery, state: FSMContext) -> None:
    """Остановить агента."""
    if _loop:
        _loop.stop()
    if _task and not _task.done():
        _task.cancel()

    await state.set_state(ChatStates.stopped)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.message.answer(
        "🛑 <b>Остановлено.</b>",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer("Останавливаю...")


@router.callback_query(F.data == CB_STOP_WRITE)
async def cb_stop_write(query: CallbackQuery, state: FSMContext) -> None:
    """Остановить и перейти в диалог."""
    if _loop:
        _loop.stop()
    if _task and not _task.done():
        _task.cancel()

    await state.set_state(ChatStates.dialog)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.message.answer(
        "🛑 Остановлено. Напиши новую задачу или инструкции.",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# СООБЩЕНИЯ ВО ВРЕМЯ РАБОТЫ АГЕНТА
# ════════════════════════════════════════════════════

@router.message(ChatStates.running)
async def handle_running_message(message: Message) -> None:
    """Пользователь написал пока агент работает."""
    await message.reply(
        "Агент сейчас работает. Используй кнопки <b>Остановить</b> или <b>Стоп + написать</b>.",
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════
# СООБЩЕНИЯ В СОСТОЯНИИ STOPPED
# ════════════════════════════════════════════════════

@router.message(ChatStates.stopped)
async def handle_stopped_message(message: Message, state: FSMContext) -> None:
    """После остановки принимаем новые сообщения."""
    await state.set_state(ChatStates.dialog)
    # Переиспользовать dialog handler
    from bot.handlers.chat import handle_dialog_message
    await handle_dialog_message(message, state, message.bot)


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

    async def log_cb(text: str) -> None:
        try:
            await send_log(bot, chat_id, text)
        except Exception:
            pass

    _loop = ReactLoop(provider=provider, log_cb=log_cb)

    plan_text_for_llm = "\n".join(
        f"{i+1}. {s.description}" for i, s in enumerate(plan.steps)
    )
    user_msg = (
        f"Выполни план:\n{plan_text_for_llm}\n\n"
        f"Реферальная ссылка: {plan.ref_url}\n"
        f"Задача: {plan.description}"
    )

    async def _run() -> None:
        try:
            result = await _loop.run(
                chat_id      = chat_id,
                user_message = user_msg,
                plan_steps   = [s.description for s in plan.steps],
            )
            # Показать финальный отчёт
            from bot.ui.report import send_final_report, save_task_result
            await send_final_report(bot, chat_id, result, plan)
            await save_task_result(plan, result)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.exception(f"[Chat] Ошибка агента: {e}")
            await send_error(bot, chat_id, str(e))
        finally:
            await state.set_state(ChatStates.dialog)
            agent_state.set_active(False)

    _task = asyncio.create_task(_run())
