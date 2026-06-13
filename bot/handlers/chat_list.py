"""
chat_list.py — Просмотр и управление LLM-чатами.

Показывает список именованных чатов пользователя.
Позволяет открыть, удалить, очистить историю и экспортировать чат.
"""

from __future__ import annotations

import io
import json
import logging

from aiogram import Router, F, Bot
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards.chat_keyboards import (
    CB_CHAT_LIST, CB_CHAT_BACK_LIST,
    CB_CHAT_OPEN, CB_CHAT_DELETE, CB_CHAT_CONFIRM,
    CB_CHAT_CLEAR_HIST, CB_CHAT_CONFIRM_HIST, CB_CHAT_EXPORT,
    chat_list_keyboard, chat_detail_keyboard,
    confirm_delete_keyboard, confirm_clear_hist_keyboard,
)
from bot.keyboards.reply_keyboard import idle_keyboard
from tools.chat_db import get_user_chats, get_chat, delete_chat, touch_chat, PROVIDER_LABELS, PROVIDER_EMOJIS, fmt_ts
from tools.history_db import clear_history, get_message_count

log    = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════
# СПИСОК ЧАТОВ
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_CHAT_LIST)
async def cb_chat_list(query: CallbackQuery) -> None:
    user_id = query.from_user.id
    chats   = await get_user_chats(user_id)

    if not chats:
        from bot.keyboards.chat_keyboards import CB_NEW_CHAT
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await query.message.edit_text(
            "💬 <b>Мои чаты</b>\n\n"
            "У тебя ещё нет чатов.\n"
            "Создай первый — каждый чат имеет свой API ключ и модель.",
            parse_mode   = "HTML",
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать чат", callback_data=CB_NEW_CHAT)],
                [InlineKeyboardButton(text="◀️ Назад",      callback_data="menu:back_main")],
            ]),
        )
        await query.answer()
        return

    await query.message.edit_text(
        f"💬 <b>Мои чаты</b>  ({len(chats)} шт.)\n\n"
        "Нажми на чат чтобы открыть или удалить.",
        parse_mode   = "HTML",
        reply_markup = chat_list_keyboard(chats),
    )
    await query.answer()


@router.callback_query(F.data == CB_CHAT_BACK_LIST)
async def cb_back_to_list(query: CallbackQuery) -> None:
    await cb_chat_list(query)


# ════════════════════════════════════════════════════
# ДЕТАЛИ ЧАТА (open без :enter = только просмотр)
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith(CB_CHAT_OPEN))
async def cb_chat_open(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    suffix = query.data[len(CB_CHAT_OPEN):]   # "123" или "123:enter"
    parts  = suffix.split(":")
    chat_id = int(parts[0])
    enter   = len(parts) > 1 and parts[1] == "enter"

    chat = await get_chat(chat_id)
    if not chat:
        await query.answer("Чат не найден", show_alert=True)
        return

    if enter:
        # Входим в чат — устанавливаем active_chat_id и переходим в dialog
        from bot.handlers.chat import ChatStates
        await touch_chat(chat_id)
        await state.set_state(ChatStates.dialog)
        await state.update_data(active_chat_id=chat_id)
        emoji = PROVIDER_EMOJIS.get(chat.provider, "🤖")
        label = PROVIDER_LABELS.get(chat.provider, chat.provider)
        await query.message.edit_text(
            f"💬 <b>{chat.name}</b>\n\n"
            f"{emoji} {label} · {chat.model or 'по умолчанию'}\n\n"
            "Агент готов к работе. Напиши задачу.",
            parse_mode   = "HTML",
        )
        await bot.send_message(
            query.message.chat.id,
            f"💬 Активный чат: <b>{chat.name}</b>",
            parse_mode   = "HTML",
            reply_markup = idle_keyboard(),
        )
        await query.answer()
        return

    # Просмотр деталей чата
    emoji = PROVIDER_EMOJIS.get(chat.provider, "🤖")
    label = PROVIDER_LABELS.get(chat.provider, chat.provider)
    await query.message.edit_text(
        f"💬 <b>{chat.name}</b>\n\n"
        f"{emoji} Провайдер: <b>{label}</b>\n"
        f"🧠 Модель: <b>{chat.model or 'по умолчанию'}</b>\n"
        f"📅 Создан: {fmt_ts(chat.created_at)}\n"
        f"🕐 Последний вход: {fmt_ts(chat.last_used)}",
        parse_mode   = "HTML",
        reply_markup = chat_detail_keyboard(chat_id),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# УДАЛЕНИЕ ЧАТА
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith(CB_CHAT_DELETE))
async def cb_chat_delete(query: CallbackQuery) -> None:
    chat_id = int(query.data[len(CB_CHAT_DELETE):])
    chat    = await get_chat(chat_id)
    if not chat:
        await query.answer("Чат не найден", show_alert=True)
        return

    await query.message.edit_text(
        f"🗑 <b>Удалить чат «{chat.name}»?</b>\n\n"
        "Это удалит чат и его API ключ. Отменить нельзя.",
        parse_mode   = "HTML",
        reply_markup = confirm_delete_keyboard(chat_id),
    )
    await query.answer()


@router.callback_query(F.data.startswith(CB_CHAT_CONFIRM))
async def cb_chat_confirm_delete(query: CallbackQuery, state: FSMContext) -> None:
    chat_id = int(query.data[len(CB_CHAT_CONFIRM):])

    # Если удаляем активный чат — сбросить active_chat_id
    data = await state.get_data()
    if data.get("active_chat_id") == chat_id:
        await state.update_data(active_chat_id=None)

    await delete_chat(chat_id)
    await query.answer("Чат удалён", show_alert=False)

    # Вернуться к списку чатов
    user_id = query.from_user.id
    chats   = await get_user_chats(user_id)

    if not chats:
        from bot.keyboards.chat_keyboards import CB_NEW_CHAT
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await query.message.edit_text(
            "💬 <b>Мои чаты</b>\n\n"
            "Нет чатов. Создай первый!",
            parse_mode   = "HTML",
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Создать чат", callback_data=CB_NEW_CHAT)],
                [InlineKeyboardButton(text="◀️ Назад",      callback_data="menu:back_main")],
            ]),
        )
    else:
        await query.message.edit_text(
            f"✅ Чат удалён.\n\n💬 <b>Мои чаты</b>  ({len(chats)} шт.)",
            parse_mode   = "HTML",
            reply_markup = chat_list_keyboard(chats),
        )


# ════════════════════════════════════════════════════
# ОЧИСТКА ИСТОРИИ
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith(CB_CHAT_CLEAR_HIST))
async def cb_clear_hist(query: CallbackQuery) -> None:
    chat_id = int(query.data[len(CB_CHAT_CLEAR_HIST):])
    chat    = await get_chat(chat_id)
    if not chat:
        await query.answer("Чат не найден", show_alert=True)
        return

    count = await get_message_count(chat_id)
    await query.message.edit_text(
        f"🧹 <b>Очистить историю «{chat.name}»?</b>\n\n"
        f"В истории {count} сообщений. После очистки агент забудет весь контекст диалога.\n\n"
        "Отменить нельзя.",
        parse_mode   = "HTML",
        reply_markup = confirm_clear_hist_keyboard(chat_id),
    )
    await query.answer()


@router.callback_query(F.data.startswith(CB_CHAT_CONFIRM_HIST))
async def cb_confirm_clear_hist(query: CallbackQuery) -> None:
    chat_id = int(query.data[len(CB_CHAT_CONFIRM_HIST):])
    chat    = await get_chat(chat_id)
    if not chat:
        await query.answer("Чат не найден", show_alert=True)
        return

    deleted = await clear_history(chat_id)
    await query.answer(f"История очищена ({deleted} сообщений)", show_alert=False)

    # Вернуться к деталям чата
    emoji = PROVIDER_EMOJIS.get(chat.provider, "🤖")
    label = PROVIDER_LABELS.get(chat.provider, chat.provider)
    await query.message.edit_text(
        f"💬 <b>{chat.name}</b>\n\n"
        f"{emoji} Провайдер: <b>{label}</b>\n"
        f"🧠 Модель: <b>{chat.model or 'по умолчанию'}</b>\n"
        f"📅 Создан: {fmt_ts(chat.created_at)}\n"
        f"🕐 Последний вход: {fmt_ts(chat.last_used)}\n\n"
        f"✅ История очищена ({deleted} сообщений удалено).",
        parse_mode   = "HTML",
        reply_markup = chat_detail_keyboard(chat_id),
    )


# ════════════════════════════════════════════════════
# ЭКСПОРТ ЧАТА
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith(CB_CHAT_EXPORT))
async def cb_export_chat(query: CallbackQuery, bot: Bot) -> None:
    chat_id = int(query.data[len(CB_CHAT_EXPORT):])
    chat    = await get_chat(chat_id)
    if not chat:
        await query.answer("Чат не найден", show_alert=True)
        return

    export_data = {
        "refagent_chat_export": True,
        "version":   1,
        "name":      chat.name,
        "provider":  chat.provider,
        "api_key":   chat.api_key,
        "api_url":   chat.api_url,
        "model":     chat.model,
    }

    json_bytes  = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
    safe_name   = "".join(c if c.isalnum() or c in "-_" else "_" for c in chat.name)
    filename    = f"chat_{safe_name}.json"

    await query.answer("Готовлю экспорт...", show_alert=False)
    await bot.send_document(
        chat_id  = query.message.chat.id,
        document = BufferedInputFile(json_bytes, filename=filename),
        caption  = (
            f"📤 <b>Экспорт чата «{chat.name}»</b>\n\n"
            "Файл содержит API ключ — храни его в безопасности.\n"
            "Для импорта отправь этот файл боту."
        ),
        parse_mode = "HTML",
    )
