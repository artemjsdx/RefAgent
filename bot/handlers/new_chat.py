"""
new_chat.py — FSM для создания нового LLM-чата.

Шаги:
  1. waiting_name     — ввод названия чата
  2. waiting_provider — выбор провайдера (inline buttons)
  3. waiting_api_key  — ввод API ключа
  4. waiting_api_url  — ввод FavoriteAPI URL (только для FA)
  5. waiting_model    — ввод модели (опционально, можно пропустить)
  → Чат создан, FSM → ChatStates.dialog + active_chat_id в state data
"""

from __future__ import annotations

import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.chat_keyboards import (
    CB_NEW_CHAT, CB_PROV_OR, CB_PROV_FA, CB_PROV_BAI,
    CB_SKIP_MODEL, CB_SKIP_URL,
    provider_picker_keyboard, skip_model_keyboard, skip_url_keyboard,
)
from bot.keyboards.reply_keyboard import idle_keyboard
from tools.chat_db import create_chat, PROVIDER_LABELS, PROVIDER_EMOJIS

log    = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ════════════════════════════════════════════════════

class NewChatStates(StatesGroup):
    waiting_name     = State()
    waiting_provider = State()
    waiting_api_key  = State()
    waiting_api_url  = State()   # только FavoriteAPI
    waiting_model    = State()


# ════════════════════════════════════════════════════
# СТАРТ — кнопка "➕ Новый чат"
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_NEW_CHAT)
async def cb_new_chat(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewChatStates.waiting_name)
    await query.message.edit_text(
        "💬 <b>Новый чат</b>\n\n"
        "Введи название для этого чата.\n"
        "<i>Например: Starfall накрутка, Тестовый, GPT-4o работа</i>",
        parse_mode = "HTML",
    )
    await query.answer()


# ════════════════════════════════════════════════════
# ШАГ 1 — Название чата
# ════════════════════════════════════════════════════

@router.message(NewChatStates.waiting_name)
async def process_chat_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name or len(name) > 64:
        await message.reply(
            "⚠️ Название должно быть от 1 до 64 символов. Попробуй снова:",
        )
        return

    await state.update_data(chat_name=name)
    await state.set_state(NewChatStates.waiting_provider)
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "🤖 Выбери LLM провайдера:",
        parse_mode   = "HTML",
        reply_markup = provider_picker_keyboard(),
    )


# ════════════════════════════════════════════════════
# ШАГ 2 — Провайдер
# ════════════════════════════════════════════════════

@router.callback_query(
    NewChatStates.waiting_provider,
    F.data.in_({CB_PROV_OR, CB_PROV_FA, CB_PROV_BAI}),
)
async def process_provider(query: CallbackQuery, state: FSMContext) -> None:
    provider_map = {
        CB_PROV_OR:  "openrouter",
        CB_PROV_FA:  "favoriteapi",
        CB_PROV_BAI: "bai",
    }
    provider = provider_map[query.data]
    emoji    = PROVIDER_EMOJIS.get(provider, "🤖")
    label    = PROVIDER_LABELS.get(provider, provider)

    await state.update_data(chat_provider=provider)

    key_hints = {
        "openrouter":  "sk-or-v1-...\n\n<i>Получить: openrouter.ai/keys</i>",
        "favoriteapi": "fa_sk_...\n\n<i>Получить у поставщика FavoriteAPI</i>",
        "bai":         "sk-...\n\n<i>Получить: b.ai/dashboard</i>",
    }

    await state.set_state(NewChatStates.waiting_api_key)
    await query.message.edit_text(
        f"✅ Провайдер: {emoji} <b>{label}</b>\n\n"
        f"🔑 Введи API ключ:\n"
        f"<code>{key_hints.get(provider, '...')}</code>",
        parse_mode = "HTML",
    )
    await query.answer()


# ════════════════════════════════════════════════════
# ШАГ 3 — API ключ
# ════════════════════════════════════════════════════

@router.message(NewChatStates.waiting_api_key)
async def process_api_key(message: Message, state: FSMContext) -> None:
    key = message.text.strip() if message.text else ""
    if len(key) < 8:
        await message.reply("⚠️ Ключ слишком короткий. Введи корректный API ключ:")
        return

    data = await state.get_data()
    provider = data.get("chat_provider", "openrouter")

    # Удалить сообщение с ключом (безопасность)
    try:
        await message.delete()
    except Exception:
        pass

    await state.update_data(chat_api_key=key)

    # FavoriteAPI требует URL
    if provider == "favoriteapi":
        await state.set_state(NewChatStates.waiting_api_url)
        await message.answer(
            "✅ API ключ сохранён.\n\n"
            "🌐 Введи базовый URL FavoriteAPI:\n"
            "<i>Например: https://your-instance.ngrok-free.app/</i>",
            parse_mode   = "HTML",
            reply_markup = skip_url_keyboard(),
        )
        return

    # Переходим к модели
    await state.update_data(chat_api_url=None)
    await _ask_model(message, state, provider)


# ════════════════════════════════════════════════════
# ШАГ 3.5 — FavoriteAPI URL (только для FA)
# ════════════════════════════════════════════════════

@router.message(NewChatStates.waiting_api_url)
async def process_api_url(message: Message, state: FSMContext) -> None:
    url = message.text.strip() if message.text else ""
    if not url.startswith("http"):
        await message.reply("⚠️ URL должен начинаться с http:// или https://")
        return

    data = await state.get_data()
    await state.update_data(chat_api_url=url)
    await _ask_model(message, state, data.get("chat_provider", "favoriteapi"))


# ════════════════════════════════════════════════════
# ШАГ 4 — Модель (опционально)
# ════════════════════════════════════════════════════

async def _ask_model(message: Message, state: FSMContext, provider: str) -> None:
    """Показать запрос на ввод модели."""
    model_hints = {
        "openrouter":  "openai/gpt-4o-mini",
        "favoriteapi": "gpt-4o-mini",
        "bai":         "kimi-k2.5",
    }
    hint = model_hints.get(provider, "gpt-4o-mini")

    await state.set_state(NewChatStates.waiting_model)
    await message.answer(
        "🧠 Выбери модель.\n\n"
        f"Введи ID модели или нажми <b>Пропустить</b> (будет использована модель по умолчанию).\n"
        f"<i>Например: <code>{hint}</code></i>",
        parse_mode   = "HTML",
        reply_markup = skip_model_keyboard(),
    )


@router.message(NewChatStates.waiting_model)
async def process_model_input(message: Message, state: FSMContext, bot: Bot) -> None:
    model = message.text.strip() if message.text else None
    await _finish_chat_creation(message, state, bot, model=model)


@router.callback_query(NewChatStates.waiting_model, F.data == CB_SKIP_MODEL)
async def cb_skip_model(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await _finish_chat_creation(query.message, state, bot, model=None, from_query=query)


# ════════════════════════════════════════════════════
# ФИНАЛ — создаём чат и переходим в dialog
# ════════════════════════════════════════════════════

async def _finish_chat_creation(
    message,
    state: FSMContext,
    bot: Bot,
    model: str | None,
    from_query=None,
) -> None:
    from bot.handlers.chat import ChatStates

    data     = await state.get_data()
    name     = data.get("chat_name", "Чат")
    provider = data.get("chat_provider", "openrouter")
    api_key  = data.get("chat_api_key", "")
    api_url  = data.get("chat_api_url")

    user_id = message.chat.id

    try:
        chat = await create_chat(
            user_id  = user_id,
            name     = name,
            provider = provider,
            api_key  = api_key,
            api_url  = api_url,
            model    = model or None,
        )
    except Exception as e:
        log.exception(f"[NewChat] Ошибка создания чата: {e}")
        target = from_query.message if from_query else message
        await target.answer(f"❌ Ошибка создания чата: {e}")
        return

    emoji   = PROVIDER_EMOJIS.get(provider, "🤖")
    label   = PROVIDER_LABELS.get(provider, provider)
    model_s = model or "по умолчанию"

    await state.set_state(ChatStates.dialog)
    await state.update_data(active_chat_id=chat.id)

    target = from_query.message if from_query else message
    await target.answer(
        f"🎉 <b>Чат создан!</b>\n\n"
        f"💬 Название:  <b>{name}</b>\n"
        f"{emoji} Провайдер: <b>{label}</b>\n"
        f"🧠 Модель:    <b>{model_s}</b>\n\n"
        f"Теперь напиши задачу — агент готов к работе.",
        parse_mode   = "HTML",
        reply_markup = idle_keyboard(),
    )
    if from_query:
        await from_query.answer()
