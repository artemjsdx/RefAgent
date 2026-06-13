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
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.reply_keyboard import (
    BTN_WRITE_TASK, BTN_MY_CHATS, BTN_CLEAR_HISTORY,
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


@router.message(F.text == BTN_CLEAR_HISTORY)
async def reply_clear_history(message: Message, state: FSMContext) -> None:
    """Кнопка "🧹 Очистить историю" — показать подтверждение с инфо о чате."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from tools.history_db import get_message_count
    from tools.chat_db import PROVIDER_LABELS, PROVIDER_EMOJIS

    data    = await state.get_data()
    chat_id = data.get("active_chat_id")

    if not chat_id:
        await message.reply(
            "💬 <b>Чат не выбран</b>\n\nОткрой чат чтобы очистить его историю.",
            parse_mode   = "HTML",
            reply_markup = idle_keyboard(),
        )
        return

    from tools.chat_db import get_chat
    chat = await get_chat(chat_id)
    if not chat:
        await message.reply("⚠️ Чат не найден.", reply_markup=idle_keyboard())
        return

    count    = await get_message_count(chat_id)
    emoji    = PROVIDER_EMOJIS.get(chat.provider, "🤖")
    label    = PROVIDER_LABELS.get(chat.provider, chat.provider)
    model    = chat.model or "по умолчанию"

    # Пояснение зачем это нужно — зависит от провайдера
    provider_notes = {
        "openrouter":  "OpenRouter — чем длиннее история, тем дороже запрос (платные модели).",
        "bai":         "b.ai — история влияет на контекст. Free plan имеет ограниченный context window.",
        "favoriteapi": "FavoriteAPI — очистка уменьшит размер контекста, отправляемого в API.",
    }
    note = provider_notes.get(chat.provider, "Очистка уменьшит контекст, отправляемый в LLM.")

    if count == 0:
        await message.answer(
            f"💬 <b>{chat.name}</b>  {emoji} {label}\n\n"
            "📭 История уже пуста — нечего очищать.",
            parse_mode   = "HTML",
            reply_markup = idle_keyboard(),
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Да, очистить ({count} сообщ.)", callback_data=f"hist:confirm:{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="hist:cancel"),
        ],
    ])

    await message.answer(
        f"🧹 <b>Очистить историю?</b>\n\n"
        f"💬 Чат: <b>{chat.name}</b>\n"
        f"{emoji} Провайдер: <b>{label}</b>\n"
        f"🧠 Модель: <b>{model}</b>\n"
        f"📨 Сообщений: <b>{count}</b>\n\n"
        f"<i>{note}</i>\n\n"
        f"⚠️ Агент забудет всю переписку и начнёт с чистого листа.",
        parse_mode   = "HTML",
        reply_markup = kb,
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


# ════════════════════════════════════════════════════
# INLINE CALLBACKS — очистка истории
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("hist:confirm:"))
async def cb_hist_confirm(query: CallbackQuery) -> None:
    """✅ Подтверждение очистки истории чата."""
    from tools.history_db import clear_history
    from tools.chat_db import get_chat, PROVIDER_EMOJIS, PROVIDER_LABELS

    chat_id = int(query.data.split(":")[-1])
    deleted = await clear_history(chat_id)

    chat  = await get_chat(chat_id)
    name  = chat.name if chat else f"#{chat_id}"
    emoji = PROVIDER_EMOJIS.get(chat.provider, "🤖") if chat else "🤖"
    label = PROVIDER_LABELS.get(chat.provider, chat.provider) if chat else ""

    await query.message.edit_text(
        f"✅ <b>История очищена</b>\n\n"
        f"💬 Чат: <b>{name}</b>  {emoji} {label}\n"
        f"🗑 Удалено сообщений: <b>{deleted}</b>\n\n"
        f"Агент начинает с чистого листа — предыдущий контекст больше не отправляется в LLM.",
        parse_mode = "HTML",
    )
    await query.answer("История очищена ✅")


@router.callback_query(F.data == "hist:cancel")
async def cb_hist_cancel(query: CallbackQuery) -> None:
    """❌ Отмена очистки — удалить панель."""
    try:
        await query.message.delete()
    except Exception:
        await query.message.edit_text("Отменено.")
    await query.answer("Отменено")
