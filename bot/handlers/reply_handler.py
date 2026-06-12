"""
reply_handler.py — Перехват нажатий reply-кнопок.

ПОРЯДОК В DISPATCHER КРИТИЧЕН:
  reply_router должен быть зарегистрирован ПЕРВЫМ — до chat_router,
  чтобы тексты reply-кнопок не попадали в хендлер свободного диалога.

Маршрутизация:
  BTN_WRITE_TASK  → переход в dialog (если агент не работает)
  BTN_STATS       → показать статистику (как CB_STATS)
  BTN_STOP        → остановить агент (как CB_STOP)
  BTN_STOP_WRITE  → остановить + перейти в dialog (как CB_STOP_WRITE)
  BTN_PLAN_RUN    → запустить план (как CB_PLAN_RUN)
  BTN_PLAN_EDIT   → редактировать план (как CB_PLAN_EDIT)
  BTN_PLAN_CANCEL → отменить план (как CB_PLAN_CANCEL)
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.keyboards.reply_keyboard import (
    BTN_WRITE_TASK, BTN_STATS,
    BTN_STOP, BTN_STOP_WRITE,
    BTN_PLAN_RUN, BTN_PLAN_EDIT, BTN_PLAN_CANCEL,
    idle_keyboard, running_keyboard,
)

log    = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════
# LAZY IMPORTS — избегаем циклических зависимостей
# ════════════════════════════════════════════════════

def _chat():
    """Lazy import chat module (избегаем circular import)."""
    import bot.handlers.chat as c
    return c


# ════════════════════════════════════════════════════
# IDLE STATE КНОПКИ
# ════════════════════════════════════════════════════

@router.message(F.text == BTN_WRITE_TASK)
async def reply_write_task(message: Message, state: FSMContext) -> None:
    """
    Кнопка "📝 Написать задачу" — переходим в dialog state.
    Если агент работает — информируем, не прерываем.
    """
    from agent.state import agent_state
    from bot.handlers.chat import ChatStates

    if agent_state.is_active:
        await message.reply(
            "⚙️ Агент сейчас работает. Нажми <b>⛔ Остановить</b> чтобы прервать.",
            parse_mode   = "HTML",
            reply_markup = running_keyboard(),
        )
        return

    await state.set_state(ChatStates.dialog)
    await message.reply(
        "Напиши задачу — реф ссылку, условия зачисления, количество аккаунтов.",
        reply_markup = idle_keyboard(),
    )


@router.message(F.text == BTN_STATS)
async def reply_stats(message: Message) -> None:
    """Кнопка "📊 Статистика" — показать статистику аккаунтов и задач."""
    from tools.db import get_all_accounts

    accounts = await get_all_accounts()
    total    = len(accounts)
    active   = sum(1 for a in accounts if a.status == "ACTIVE")
    frozen   = sum(1 for a in accounts if a.status == "FROZEN")
    cond     = sum(1 for a in accounts if a.is_conductor)

    await message.reply(
        "<b>Статистика</b>\n\n"
        "<pre>"
        f"{'Аккаунтов в пуле':<22} {total}\n"
        f"{'  активных':<22} {active}\n"
        f"{'  замороженных':<22} {frozen}\n"
        f"{'  проводников':<22} {cond}\n"
        "</pre>",
        parse_mode   = "HTML",
        reply_markup = idle_keyboard(),
    )


# ════════════════════════════════════════════════════
# RUNNING STATE КНОПКИ
# ════════════════════════════════════════════════════

@router.message(F.text == BTN_STOP)
async def reply_stop(message: Message, state: FSMContext, bot: Bot) -> None:
    """Кнопка "⛔ Остановить" — остановить агента."""
    from agent.state import agent_state
    from bot.handlers.chat import ChatStates, _stop_loop, _get_task

    _stop_loop()
    task = _get_task()
    if task and not task.done():
        task.cancel()

    agent_state.set_active(False)
    await state.set_state(ChatStates.stopped)
    await message.reply(
        "🛑 <b>Остановлено.</b>",
        parse_mode   = "HTML",
        reply_markup = idle_keyboard(),
    )


@router.message(F.text == BTN_STOP_WRITE)
async def reply_stop_write(message: Message, state: FSMContext, bot: Bot) -> None:
    """Кнопка "✏️ Стоп + написать" — остановить и перейти в dialog."""
    from agent.state import agent_state
    from bot.handlers.chat import ChatStates, _stop_loop, _get_task

    _stop_loop()
    task = _get_task()
    if task and not task.done():
        task.cancel()

    agent_state.set_active(False)
    await state.set_state(ChatStates.dialog)
    await message.reply(
        "🛑 Остановлено. Напиши новую задачу.",
        parse_mode   = "HTML",
        reply_markup = idle_keyboard(),
    )


# ════════════════════════════════════════════════════
# PLAN STATE КНОПКИ
# ════════════════════════════════════════════════════

@router.message(F.text == BTN_PLAN_RUN)
async def reply_plan_run(message: Message, state: FSMContext, bot: Bot) -> None:
    """Кнопка "✅ Запустить план" — запустить текущий план."""
    from agent.state import agent_state
    from agent.plan_manager import plan_manager
    from bot.handlers.chat import ChatStates, _start_agent_task
    from bot.ui.status_blocks import send_error
    from config.settings import get_settings
    from providers import build_provider
    from bot.keyboards.main_menu import task_controls_keyboard

    if agent_state.is_active:
        await message.reply("Агент уже работает.", reply_markup=running_keyboard())
        return

    plan = plan_manager.plan
    if not plan:
        await message.reply("План не найден. Напиши задачу заново.", reply_markup=idle_keyboard())
        return

    await state.set_state(ChatStates.running)
    chat_id = message.chat.id

    await message.reply("🚀 <b>Задача запущена</b>", parse_mode="HTML", reply_markup=running_keyboard())
    await bot.send_message(
        chat_id,
        "⚙️ Агент работает...",
        reply_markup = task_controls_keyboard(),
    )

    settings = get_settings()
    try:
        provider = build_provider(settings)
    except ValueError as e:
        await send_error(bot, chat_id, f"Провайдер не настроен: {e}")
        await state.set_state(ChatStates.dialog)
        return

    await _start_agent_task(bot, chat_id, state, provider, plan)


@router.message(F.text == BTN_PLAN_EDIT)
async def reply_plan_edit(message: Message, state: FSMContext) -> None:
    """Кнопка "✏️ Изменить" — вернуться в диалог для редактирования плана."""
    from bot.handlers.chat import ChatStates

    await state.set_state(ChatStates.dialog)
    await message.reply(
        "✏️ Напиши что нужно изменить — агент пересоставит план.",
        reply_markup = idle_keyboard(),
    )


@router.message(F.text == BTN_PLAN_CANCEL)
async def reply_plan_cancel(message: Message, state: FSMContext) -> None:
    """Кнопка "❌ Отмена" — отменить план."""
    from agent.plan_manager import plan_manager
    from bot.handlers.chat import ChatStates

    await plan_manager.cancel()
    await state.set_state(ChatStates.dialog)
    await message.reply("Задача отменена.", reply_markup=idle_keyboard())
