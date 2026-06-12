"""
reply_handler.py — Перехват нажатий reply-кнопок.

ПОРЯДОК В DISPATCHER КРИТИЧЕН:
  reply_router должен быть зарегистрирован ПЕРВЫМ — до chat_router,
  чтобы тексты reply-кнопок не попадали в хендлер свободного диалога.

Маршрутизация:
  BTN_WRITE_TASK  → переход в dialog (если агент не работает)
  BTN_MY_CHATS    → показать список чатов
  BTN_STOP        → остановить агент
  BTN_STOP_WRITE  → остановить + перейти в dialog
  BTN_PLAN_RUN    → запустить план
  BTN_PLAN_EDIT   → редактировать план
  BTN_PLAN_CANCEL → отменить план
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.keyboards.reply_keyboard import (
    BTN_WRITE_TASK, BTN_MY_CHATS,
    BTN_STOP, BTN_STOP_WRITE,
    BTN_PLAN_RUN, BTN_PLAN_EDIT, BTN_PLAN_CANCEL,
    idle_keyboard, running_keyboard,
)

log    = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════
# IDLE STATE
# ════════════════════════════════════════════════════

@router.message(F.text == BTN_WRITE_TASK)
async def reply_write_task(message: Message, state: FSMContext) -> None:
    from agent.state import agent_state
    from bot.handlers.chat import ChatStates

    if agent_state.is_active:
        await message.reply(
            "⚙️ Агент сейчас работает. Нажми <b>⛔ Остановить</b> чтобы прервать.",
            parse_mode   = "HTML",
            reply_markup = running_keyboard(),
        )
        return

    # Проверить — есть ли активный чат
    data = await state.get_data()
    if not data.get("active_chat_id"):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await message.reply(
            "💬 <b>Сначала выбери чат</b>\n\n"
            "Нажми <b>💬 Мои чаты</b> чтобы открыть существующий,\n"
            "или <b>➕ Новый чат</b> чтобы создать с нуля.",
            parse_mode   = "HTML",
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Новый чат",  callback_data="chat:new")],
                [InlineKeyboardButton(text="💬 Мои чаты",   callback_data="chat:list")],
            ]),
        )
        return

    await state.set_state(ChatStates.dialog)
    await message.reply(
        "📝 Напиши задачу — реф ссылку, условия зачисления, количество аккаунтов.",
        reply_markup = idle_keyboard(),
    )


@router.message(F.text == BTN_MY_CHATS)
async def reply_my_chats(message: Message) -> None:
    """Кнопка "💬 Мои чаты" — показать список через inline меню."""
    from tools.chat_db import get_user_chats, PROVIDER_EMOJIS, fmt_ts
    from bot.keyboards.chat_keyboards import chat_list_keyboard, CB_NEW_CHAT
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    user_id = message.chat.id
    chats   = await get_user_chats(user_id)

    if not chats:
        await message.answer(
            "💬 <b>Мои чаты</b>\n\nУ тебя ещё нет чатов. Создай первый!",
            parse_mode   = "HTML",
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать чат", callback_data=CB_NEW_CHAT)],
            ]),
        )
        return

    await message.answer(
        f"💬 <b>Мои чаты</b>  ({len(chats)} шт.)\n\nНажми на чат чтобы открыть.",
        parse_mode   = "HTML",
        reply_markup = chat_list_keyboard(chats),
    )


# ════════════════════════════════════════════════════
# RUNNING STATE
# ════════════════════════════════════════════════════

@router.message(F.text == BTN_STOP)
async def reply_stop(message: Message, state: FSMContext, bot: Bot) -> None:
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
# PLAN STATE
# ════════════════════════════════════════════════════

@router.message(F.text == BTN_PLAN_RUN)
async def reply_plan_run(message: Message, state: FSMContext, bot: Bot) -> None:
    from agent.state import agent_state
    from agent.plan_manager import plan_manager
    from bot.handlers.chat import ChatStates, _start_agent_task, _load_active_chat
    from bot.ui.status_blocks import send_error
    from providers import build_provider_from_chat
    from bot.keyboards.main_menu import task_controls_keyboard

    if agent_state.is_active:
        await message.reply("Агент уже работает.", reply_markup=running_keyboard())
        return

    plan = plan_manager.plan
    if not plan:
        await message.reply("Plan not found. Напиши задачу заново.", reply_markup=idle_keyboard())
        return

    chat = await _load_active_chat(state)
    if not chat:
        await message.reply("💬 Чат не выбран.", reply_markup=idle_keyboard())
        return

    await state.set_state(ChatStates.running)
    chat_id = message.chat.id

    await message.reply("🚀 <b>Задача запущена</b>", parse_mode="HTML", reply_markup=running_keyboard())
    await bot.send_message(
        chat_id,
        "⚙️ Агент работает...",
        reply_markup = task_controls_keyboard(),
    )

    try:
        provider = build_provider_from_chat(chat)
    except ValueError as e:
        await send_error(bot, chat_id, f"Провайдер не настроен: {e}")
        await state.set_state(ChatStates.dialog)
        return

    await _start_agent_task(bot, chat_id, state, provider, plan)


@router.message(F.text == BTN_PLAN_EDIT)
async def reply_plan_edit(message: Message, state: FSMContext) -> None:
    from bot.handlers.chat import ChatStates
    await state.set_state(ChatStates.dialog)
    await message.reply(
        "✏️ Напиши что нужно изменить — агент пересоставит план.",
        reply_markup = idle_keyboard(),
    )


@router.message(F.text == BTN_PLAN_CANCEL)
async def reply_plan_cancel(message: Message, state: FSMContext) -> None:
    from agent.plan_manager import plan_manager
    from bot.handlers.chat import ChatStates
    await plan_manager.cancel()
    await state.set_state(ChatStates.dialog)
    await message.reply("❌ Задача отменена.", reply_markup=idle_keyboard())
