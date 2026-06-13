"""
new_chat.py — FSM для создания нового LLM-чата.

Шаги:
  1. waiting_name     — ввод названия чата
  2. waiting_provider — выбор провайдера (inline buttons)
  3. waiting_api_key  — ввод API ключа
  4. waiting_api_url  — ввод FavoriteAPI URL (только для FA)
  5. waiting_model    — ввод модели или браузер (OpenRouter: paginated)
  → Чат создан, FSM → ChatStates.dialog + active_chat_id в state data

OpenRouter: на шаге 5 доступен браузер моделей (бесплатные/платные/ручной ввод).
Callback prefix: ncm: (new chat model) — не пересекается с settings-browser.
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
from config.constants import MODELS_PER_PAGE

# ────────────────────────────────────────────────────
# Callback prefix для браузера моделей в new_chat FSM.
# Изолирован от settings_menu (там prefix "models:").
# ────────────────────────────────────────────────────
_NCM_FREE   = "ncm:free:"     # + page
_NCM_PAID   = "ncm:paid:"     # + page
_NCM_SELECT = "ncm:select:"   # + model_id
_NCM_MANUAL = "ncm:manual"    # переключиться на ручной ввод
_NCM_NOOP   = "ncm:noop"      # индикатор страницы (игнорировать)

# b.ai model browser (New Chat b.ai Model)
_BCM_FREE   = "bcm:free:"
_BCM_PAID   = "bcm:paid:"
_BCM_SELECT = "bcm:select:"
_BCM_MANUAL = "bcm:manual"
_BCM_NOOP   = "bcm:noop"

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
    """Показать запрос на ввод модели. OpenRouter — браузер + ручной ввод."""
    await state.set_state(NewChatStates.waiting_model)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    if provider == "openrouter":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Бесплатные модели",            callback_data=f"{_NCM_FREE}0")],
            [InlineKeyboardButton(text="💳 Платные модели",               callback_data=f"{_NCM_PAID}0")],
            [InlineKeyboardButton(text="⌨️ Ввести ID вручную",           callback_data=_NCM_MANUAL)],
            [InlineKeyboardButton(text="⏭ Пропустить (deepseek-r1:free)", callback_data=CB_SKIP_MODEL)],
        ])
        await message.answer(
            "🧠 <b>Выбери модель OpenRouter</b>\n\n"
            "Просмотри список или введи ID вручную.\n"
            "По умолчанию: <code>deepseek/deepseek-r1-0528:free</code>",
            parse_mode   = "HTML",
            reply_markup = kb,
        )
    elif provider == "bai":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Бесплатные модели",   callback_data=f"{_BCM_FREE}0")],
            [InlineKeyboardButton(text="💳 Платные модели",      callback_data=f"{_BCM_PAID}0")],
            [InlineKeyboardButton(text="⌨️ Ввести ID вручную",  callback_data=_BCM_MANUAL)],
            [InlineKeyboardButton(text="⏭ Пропустить (kimi-k2.5)", callback_data=CB_SKIP_MODEL)],
        ])
        await message.answer(
            "🧠 <b>Выбери модель b.ai</b>\n\n"
            "Бесплатный план: <code>kimi-k2.5</code>, <code>glm-5</code>, <code>glm-5.1</code>\n"
            "По умолчанию: <code>kimi-k2.5</code>",
            parse_mode   = "HTML",
            reply_markup = kb,
        )
    else:
        # FavoriteAPI — только ручной ввод
        await message.answer(
            "🧠 Выбери модель.\n\n"
            "Введи ID модели или нажми <b>Пропустить</b> (будет использована модель по умолчанию).\n"
            "<i>Например: <code>gpt-4o-mini</code></i>",
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
# БРАУЗЕР МОДЕЛЕЙ OPENROUTER (в контексте создания чата)
# prefix ncm: — New Chat Model
# ════════════════════════════════════════════════════

@router.callback_query(
    NewChatStates.waiting_model,
    F.data.func(lambda d: d.startswith("ncm:free:") or d.startswith("ncm:paid:")),
)
async def cb_ncm_page(query: CallbackQuery, state: FSMContext) -> None:
    d = query.data
    if d.startswith(_NCM_FREE):
        tier = "free"
        page = int(d[len(_NCM_FREE):])
    else:
        tier = "paid"
        page = int(d[len(_NCM_PAID):])

    data    = await state.get_data()
    api_key = data.get("chat_api_key", "")
    models  = await _ncm_fetch_models(api_key)
    if not models:
        await query.answer("Не удалось загрузить модели. Введи ID вручную.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    filtered    = [m for m in models if (m.is_free if tier == "free" else not m.is_free)]
    total       = len(filtered)
    total_pages = max(1, (total + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE)
    start       = page * MODELS_PER_PAGE
    end         = min(start + MODELS_PER_PAGE, total)
    page_models = filtered[start:end]

    rows = []
    for m in page_models:
        if m.is_free:
            price_str = "free"
        elif m.price_prompt is not None:
            price_str = f"${m.price_prompt:.2f}/1M"
        else:
            price_str = "paid"
        name = m.name[:26] if len(m.name) > 26 else m.name
        rows.append([InlineKeyboardButton(
            text          = f"{name} [{price_str}]",
            callback_data = f"{_NCM_SELECT}{m.id}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"ncm:{tier}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=_NCM_NOOP))
    if end < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"ncm:{tier}:{page + 1}"))
    if nav:
        rows.append(nav)

    tier_label = "Бесплатные" if tier == "free" else "Платные"
    rows.append([InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data=_NCM_MANUAL)])
    rows.append([InlineKeyboardButton(text="⏭ Пропустить (по умолчанию)", callback_data=CB_SKIP_MODEL)])

    await query.message.edit_text(
        f"🧠 <b>Модели OpenRouter — {tier_label}</b>\n"
        f"Страница {page + 1} из {total_pages} | Всего: {total}",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await query.answer()


@router.callback_query(NewChatStates.waiting_model, F.data.startswith(_NCM_SELECT))
async def cb_ncm_select(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    model_id = query.data[len(_NCM_SELECT):]
    await _finish_chat_creation(query.message, state, bot, model=model_id, from_query=query)


@router.callback_query(NewChatStates.waiting_model, F.data == _NCM_MANUAL)
async def cb_ncm_manual(query: CallbackQuery, state: FSMContext) -> None:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить (по умолчанию)", callback_data=CB_SKIP_MODEL)],
    ])
    await query.message.edit_text(
        "⌨️ <b>Ввод ID модели вручную</b>\n\n"
        "Введи ID модели:\n"
        "<i>Например: <code>deepseek/deepseek-r1-0528:free</code></i>\n\n"
        "<a href='https://openrouter.ai/models'>Список моделей OpenRouter</a>",
        parse_mode   = "HTML",
        reply_markup = kb,
        disable_web_page_preview = True,
    )
    await query.answer()


@router.callback_query(NewChatStates.waiting_model, F.data == _NCM_NOOP)
async def cb_ncm_noop(query: CallbackQuery) -> None:
    await query.answer()


async def _ncm_fetch_models(api_key: str):
    """Получить модели OpenRouter используя api_key из FSM state."""
    try:
        from providers.openrouter import OpenRouterProvider
        p = OpenRouterProvider(api_key=api_key)
        return await p.get_models()
    except Exception as e:
        log.warning(f"[NewChat] Не удалось загрузить модели OR: {e}")
        return []


# ════════════════════════════════════════════════════
# БРАУЗЕР МОДЕЛЕЙ b.ai (в контексте создания чата)
# prefix bcm: — B.ai Chat Model
# ════════════════════════════════════════════════════

@router.callback_query(
    NewChatStates.waiting_model,
    F.data.func(lambda d: d.startswith("bcm:free:") or d.startswith("bcm:paid:")),
)
async def cb_bcm_page(query: CallbackQuery, state: FSMContext) -> None:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    d = query.data
    if d.startswith(_BCM_FREE):
        tier = "free"
        page = int(d[len(_BCM_FREE):])
    else:
        tier = "paid"
        page = int(d[len(_BCM_PAID):])

    data    = await state.get_data()
    api_key = data.get("chat_api_key", "")
    models  = await _bcm_fetch_models(api_key)

    if not models:
        await query.answer("Не удалось загрузить модели. Введи ID вручную.", show_alert=True)
        return

    filtered    = [m for m in models if (m.is_free if tier == "free" else not m.is_free)]
    total       = len(filtered)
    total_pages = max(1, (total + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE)
    start       = page * MODELS_PER_PAGE
    end         = min(start + MODELS_PER_PAGE, total)
    page_models = filtered[start:end]

    rows = []
    for m in page_models:
        price_str = "free" if m.is_free else "paid"
        name = m.name[:28] if len(m.name) > 28 else m.name
        rows.append([InlineKeyboardButton(
            text          = f"{name} [{price_str}]",
            callback_data = f"{_BCM_SELECT}{m.id}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"bcm:{tier}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=_BCM_NOOP))
    if end < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"bcm:{tier}:{page + 1}"))
    if nav:
        rows.append(nav)

    tier_label = "Бесплатные" if tier == "free" else "Платные"
    rows.append([InlineKeyboardButton(text="⌨️ Ввести вручную",      callback_data=_BCM_MANUAL)])
    rows.append([InlineKeyboardButton(text="⏭ Пропустить (kimi-k2.5)", callback_data=CB_SKIP_MODEL)])

    await query.message.edit_text(
        f"🧠 <b>Модели b.ai — {tier_label}</b>\n"
        f"Страница {page + 1} из {total_pages} | Всего: {total}",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await query.answer()


@router.callback_query(NewChatStates.waiting_model, F.data.startswith(_BCM_SELECT))
async def cb_bcm_select(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    model_id = query.data[len(_BCM_SELECT):]
    await _finish_chat_creation(query.message, state, bot, model=model_id, from_query=query)


@router.callback_query(NewChatStates.waiting_model, F.data == _BCM_MANUAL)
async def cb_bcm_manual(query: CallbackQuery, state: FSMContext) -> None:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить (kimi-k2.5)", callback_data=CB_SKIP_MODEL)],
    ])
    await query.message.edit_text(
        "⌨️ <b>Ввод ID модели вручную</b>\n\n"
        "Введи ID модели:\n"
        "<i>Например: <code>kimi-k2.5</code>, <code>glm-5</code></i>\n\n"
        "<a href='https://b.ai'>Доступные модели: b.ai</a>",
        parse_mode               = "HTML",
        reply_markup             = kb,
        disable_web_page_preview = True,
    )
    await query.answer()


@router.callback_query(NewChatStates.waiting_model, F.data == _BCM_NOOP)
async def cb_bcm_noop(query: CallbackQuery) -> None:
    await query.answer()


async def _bcm_fetch_models(api_key: str):
    """Получить модели b.ai используя api_key из FSM state."""
    try:
        from providers.bai import BaiProvider
        p = BaiProvider(api_key=api_key)
        return await p.get_models()
    except Exception as e:
        log.warning(f"[NewChat] Не удалось загрузить модели b.ai: {e}")
        return []


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
