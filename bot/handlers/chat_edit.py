"""
chat_edit.py — FSM редактирования настроек существующего чата.

Позволяет менять:
  • Название чата
  • API ключ
  • Модель (с браузером для OpenRouter)

Флоу:
  chat:edit:<id>  →  выбор поля  →  ввод значения  →  сохранено
"""

from __future__ import annotations

import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from tools.chat_db import get_chat, update_chat_fields, PROVIDER_LABELS, PROVIDER_EMOJIS, fmt_ts
from bot.keyboards.chat_keyboards import (
    CB_CHAT_EDIT, CB_CHAT_BACK_LIST,
    chat_detail_keyboard,
)

log    = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ════════════════════════════════════════════════════

class ChatEditStates(StatesGroup):
    choosing_field = State()    # показываем меню полей
    editing_name   = State()    # ждём новое название
    editing_apikey = State()    # ждём новый API ключ
    editing_model  = State()    # ждём ввод модели (или выбор через browser)
    browsing_model = State()    # браузер моделей (только OpenRouter)


# ════════════════════════════════════════════════════
# CALLBACK CONSTANTS (локальные, только для редактирования)
# ════════════════════════════════════════════════════

_CB_FIELD_NAME   = "cedit:field:name"
_CB_FIELD_APIKEY = "cedit:field:apikey"
_CB_FIELD_MODEL  = "cedit:field:model"
_CB_CANCEL       = "cedit:cancel"
_CB_MODEL_BROWSE = "cedit:mbrowse"        # открыть браузер моделей
_CB_MODEL_MANUAL = "cedit:mmanual"        # ручной ввод модели
_CB_MB_FREE      = "cedit:mb:free:"       # + page
_CB_MB_PAID      = "cedit:mb:paid:"       # + page
_CB_MB_SELECT    = "cedit:mb:select:"     # + model_id
_CB_MB_NOOP      = "cedit:mb:noop"
_CB_MODEL_RESET  = "cedit:model:reset"    # сбросить на умолчание провайдера


# ════════════════════════════════════════════════════
# ВХОД — кнопка "✏️ Изменить" в деталях чата
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith(CB_CHAT_EDIT))
async def cb_edit_chat(query: CallbackQuery, state: FSMContext) -> None:
    chat_id = int(query.data[len(CB_CHAT_EDIT):])
    chat    = await get_chat(chat_id)
    if not chat:
        await query.answer("Чат не найден", show_alert=True)
        return

    await state.set_state(ChatEditStates.choosing_field)
    await state.update_data(edit_chat_id=chat_id, edit_provider=chat.provider)

    emoji = PROVIDER_EMOJIS.get(chat.provider, "🤖")
    label = PROVIDER_LABELS.get(chat.provider, chat.provider)
    await query.message.edit_text(
        f"✏️ <b>Редактировать чат</b>\n\n"
        f"💬 Название: <b>{chat.name}</b>\n"
        f"{emoji} Провайдер: <b>{label}</b>\n"
        f"🧠 Модель: <b>{chat.model or 'по умолчанию'}</b>\n\n"
        "Что хочешь изменить?",
        parse_mode   = "HTML",
        reply_markup = _field_picker_keyboard(chat_id),
    )
    await query.answer()


def _field_picker_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Название",  callback_data=_CB_FIELD_NAME)],
        [InlineKeyboardButton(text="🔑 API ключ",  callback_data=_CB_FIELD_APIKEY)],
        [InlineKeyboardButton(text="🧠 Модель",    callback_data=_CB_FIELD_MODEL)],
        [InlineKeyboardButton(text="◀️ Назад",    callback_data=f"chat:open:{chat_id}")],
    ])


# ════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ НАЗВАНИЯ
# ════════════════════════════════════════════════════

@router.callback_query(ChatEditStates.choosing_field, F.data == _CB_FIELD_NAME)
async def cb_edit_name(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChatEditStates.editing_name)
    data    = await state.get_data()
    chat_id = data["edit_chat_id"]
    await query.message.edit_text(
        "💬 <b>Новое название чата</b>\n\n"
        "Введи название (1–64 символа):",
        parse_mode   = "HTML",
        reply_markup = _cancel_keyboard(chat_id),
    )
    await query.answer()


@router.message(ChatEditStates.editing_name)
async def process_edit_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip() if message.text else ""
    if not name or len(name) > 64:
        await message.reply("⚠️ Название должно быть от 1 до 64 символов. Попробуй снова:")
        return

    data    = await state.get_data()
    chat_id = data["edit_chat_id"]
    await update_chat_fields(chat_id, name=name)
    chat = await get_chat(chat_id)

    await state.set_state(ChatEditStates.choosing_field)
    await message.answer(
        f"✅ Название изменено на <b>{name}</b>\n\nЧто ещё хочешь изменить?",
        parse_mode   = "HTML",
        reply_markup = _field_picker_keyboard(chat_id),
    )


# ════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ API КЛЮЧА
# ════════════════════════════════════════════════════

@router.callback_query(ChatEditStates.choosing_field, F.data == _CB_FIELD_APIKEY)
async def cb_edit_apikey(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChatEditStates.editing_apikey)
    data    = await state.get_data()
    chat_id = data["edit_chat_id"]
    await query.message.edit_text(
        "🔑 <b>Новый API ключ</b>\n\n"
        "Введи новый ключ для этого чата.\n"
        "<i>Сообщение с ключом будет автоматически удалено.</i>",
        parse_mode   = "HTML",
        reply_markup = _cancel_keyboard(chat_id),
    )
    await query.answer()


@router.message(ChatEditStates.editing_apikey)
async def process_edit_apikey(message: Message, state: FSMContext) -> None:
    key = message.text.strip() if message.text else ""
    if len(key) < 8:
        await message.reply("⚠️ Ключ слишком короткий. Введи корректный API ключ:")
        return

    # Удалить сообщение с ключом (безопасность)
    try:
        await message.delete()
    except Exception:
        pass

    data    = await state.get_data()
    chat_id = data["edit_chat_id"]
    await update_chat_fields(chat_id, api_key=key)

    await state.set_state(ChatEditStates.choosing_field)
    await message.answer(
        "✅ API ключ обновлён.\n\nЧто ещё хочешь изменить?",
        parse_mode   = "HTML",
        reply_markup = _field_picker_keyboard(chat_id),
    )


# ════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ МОДЕЛИ — выбор способа
# ════════════════════════════════════════════════════

@router.callback_query(ChatEditStates.choosing_field, F.data == _CB_FIELD_MODEL)
async def cb_edit_model(query: CallbackQuery, state: FSMContext) -> None:
    data     = await state.get_data()
    chat_id  = data["edit_chat_id"]
    provider = data.get("edit_provider", "openrouter")

    if provider == "openrouter":
        # Для OpenRouter предлагаем браузер или ручной ввод
        await state.set_state(ChatEditStates.editing_model)
        await query.message.edit_text(
            "🧠 <b>Изменить модель</b>\n\n"
            "Для OpenRouter можно выбрать из списка (300+ моделей) "
            "или ввести ID вручную.",
            parse_mode   = "HTML",
            reply_markup = _model_method_keyboard(chat_id),
        )
    else:
        # Для FA / b.ai — только ручной ввод
        await state.set_state(ChatEditStates.editing_model)
        hint = "kimi-k2.5" if provider == "bai" else "gpt-4o-mini"
        await query.message.edit_text(
            f"🧠 <b>Новая модель</b>\n\n"
            f"Введи ID модели.\n"
            f"<i>Например: <code>{hint}</code></i>\n\n"
            f"Или нажми <b>Сбросить</b> чтобы использовать модель по умолчанию.",
            parse_mode   = "HTML",
            reply_markup = _model_input_keyboard(chat_id, show_reset=True),
        )
    await query.answer()


def _model_method_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Бесплатные",  callback_data=f"{_CB_MB_FREE}0")],
        [InlineKeyboardButton(text="💳 Платные",     callback_data=f"{_CB_MB_PAID}0")],
        [InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data=_CB_MODEL_MANUAL)],
        [InlineKeyboardButton(text="🔄 Сбросить (по умолчанию)", callback_data=_CB_MODEL_RESET)],
        [InlineKeyboardButton(text="◀️ Назад",       callback_data=f"chat:open:{chat_id}")],
    ])


def _model_input_keyboard(chat_id: int, show_reset: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if show_reset:
        rows.append([InlineKeyboardButton(text="🔄 Сбросить (по умолчанию)", callback_data=_CB_MODEL_RESET)])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"chat:open:{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════
# РУЧНОЙ ВВОД МОДЕЛИ
# ════════════════════════════════════════════════════

@router.callback_query(ChatEditStates.editing_model, F.data == _CB_MODEL_MANUAL)
async def cb_model_manual(query: CallbackQuery, state: FSMContext) -> None:
    data    = await state.get_data()
    chat_id = data["edit_chat_id"]
    await query.message.edit_text(
        "⌨️ <b>Ввод модели вручную</b>\n\n"
        "Введи ID модели:\n"
        "<i>Например: <code>deepseek/deepseek-r1-0528:free</code></i>",
        parse_mode   = "HTML",
        reply_markup = _model_input_keyboard(chat_id, show_reset=True),
    )
    await query.answer()


@router.message(ChatEditStates.editing_model)
async def process_edit_model_text(message: Message, state: FSMContext) -> None:
    model   = message.text.strip() if message.text else ""
    data    = await state.get_data()
    chat_id = data["edit_chat_id"]

    if not model:
        await message.reply("⚠️ Введи ID модели или нажми 'Сбросить'.")
        return

    await update_chat_fields(chat_id, model=model)
    await state.set_state(ChatEditStates.choosing_field)
    await message.answer(
        f"✅ Модель изменена на <code>{model}</code>\n\nЧто ещё хочешь изменить?",
        parse_mode   = "HTML",
        reply_markup = _field_picker_keyboard(chat_id),
    )


# ════════════════════════════════════════════════════
# СБРОС МОДЕЛИ НА УМОЛЧАНИЕ
# ════════════════════════════════════════════════════

@router.callback_query(
    F.data == _CB_MODEL_RESET,
    ChatEditStates.editing_model,
)
async def cb_model_reset(query: CallbackQuery, state: FSMContext) -> None:
    data    = await state.get_data()
    chat_id = data["edit_chat_id"]
    await update_chat_fields(chat_id, model=None)
    await state.set_state(ChatEditStates.choosing_field)
    await query.message.edit_text(
        "✅ Модель сброшена — будет использоваться <b>модель по умолчанию</b> провайдера.\n\n"
        "Что ещё хочешь изменить?",
        parse_mode   = "HTML",
        reply_markup = _field_picker_keyboard(chat_id),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# БРАУЗЕР МОДЕЛЕЙ OPENROUTER (в контексте редактирования)
# ════════════════════════════════════════════════════

@router.callback_query(
    ChatEditStates.editing_model,
    F.data.func(lambda d: d.startswith(_CB_MB_FREE) or d.startswith(_CB_MB_PAID)),
)
async def cb_mb_page(query: CallbackQuery, state: FSMContext) -> None:
    data     = await state.get_data()
    chat_id  = data["edit_chat_id"]
    provider = data.get("edit_provider", "openrouter")

    if d := query.data:
        if d.startswith(_CB_MB_FREE):
            tier = "free"
            page = int(d[len(_CB_MB_FREE):])
        else:
            tier = "paid"
            page = int(d[len(_CB_MB_PAID):])

    models = await _fetch_or_models(chat_id)
    if not models:
        await query.answer("Не удалось загрузить список моделей", show_alert=True)
        return

    from config.constants import MODELS_PER_PAGE
    filtered    = [m for m in models if (m.is_free if tier == "free" else not m.is_free)]
    total       = len(filtered)
    total_pages = max(1, (total + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE)
    start       = page * MODELS_PER_PAGE
    end         = min(start + MODELS_PER_PAGE, total)
    page_models = filtered[start:end]

    chat        = await get_chat(chat_id)
    active_model = chat.model if chat else None

    rows = []
    for m in page_models:
        marker = "✅ " if m.id == active_model else ""
        if m.is_free:
            price_str = "free"
        elif m.price_prompt is not None:
            price_str = f"${m.price_prompt:.2f}/1M"
        else:
            price_str = "paid"
        name = m.name[:26] if len(m.name) > 26 else m.name
        rows.append([InlineKeyboardButton(
            text          = f"{marker}{name} [{price_str}]",
            callback_data = f"{_CB_MB_SELECT}{m.id}",
        )])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"cedit:mb:{tier}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=_CB_MB_NOOP))
    if end < total:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"cedit:mb:{tier}:{page + 1}"))
    if nav:
        rows.append(nav)

    tier_label = "Бесплатные" if tier == "free" else "Платные"
    rows.append([InlineKeyboardButton(text="⌨️ Ввести вручную", callback_data=_CB_MODEL_MANUAL)])
    rows.append([InlineKeyboardButton(text="🔄 Сбросить",        callback_data=_CB_MODEL_RESET)])
    rows.append([InlineKeyboardButton(text="◀️ Назад",           callback_data=f"chat:open:{chat_id}")])

    await query.message.edit_text(
        f"🧠 <b>Модели OpenRouter — {tier_label}</b>\n"
        f"Страница {page + 1} из {total_pages} | Всего: {total}",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await query.answer()


@router.callback_query(ChatEditStates.editing_model, F.data.startswith(_CB_MB_SELECT))
async def cb_mb_select(query: CallbackQuery, state: FSMContext) -> None:
    model_id = query.data[len(_CB_MB_SELECT):]
    data     = await state.get_data()
    chat_id  = data["edit_chat_id"]

    await update_chat_fields(chat_id, model=model_id)
    await state.set_state(ChatEditStates.choosing_field)
    short = model_id.split("/")[-1] if "/" in model_id else model_id
    await query.message.edit_text(
        f"✅ Модель выбрана: <code>{short}</code>\n\nЧто ещё хочешь изменить?",
        parse_mode   = "HTML",
        reply_markup = _field_picker_keyboard(chat_id),
    )
    await query.answer("Сохранено")


@router.callback_query(ChatEditStates.editing_model, F.data == _CB_MB_NOOP)
async def cb_mb_noop(query: CallbackQuery) -> None:
    await query.answer()


# ════════════════════════════════════════════════════
# ОТМЕНА
# ════════════════════════════════════════════════════

@router.callback_query(F.data == _CB_CANCEL)
async def cb_cancel(query: CallbackQuery, state: FSMContext) -> None:
    data    = await state.get_data()
    chat_id = data.get("edit_chat_id")
    await state.clear()
    if chat_id:
        # Вернуться к деталям чата
        chat = await get_chat(chat_id)
        if chat:
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
            return
    await query.answer("Отменено")


# ════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════

async def _fetch_or_models(chat_id: int):
    """Получить список моделей OpenRouter для браузера, используя api_key из чата."""
    try:
        from providers.openrouter import OpenRouterProvider
        chat = await get_chat(chat_id)
        api_key = chat.api_key if chat else ""
        p = OpenRouterProvider(api_key=api_key)
        return await p.get_models()
    except Exception as e:
        log.warning(f"[ChatEdit] Не удалось загрузить модели OR: {e}")
        return []


def _cancel_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"chat:open:{chat_id}")],
    ])
