"""
settings_menu.py — Settings screen handlers for RefAgent.

Handles:
- Provider selection (OpenRouter / FavoriteAPI)
- Model browser (paginated, Free/Paid filter)
- Manual model input via FSM state
- Connection health check

GUARD: provider/model changes are blocked while agent_state.is_active == True.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.main_menu import (
    settings_keyboard, provider_select_keyboard,
    CB_SETTINGS, CB_SETTINGS_PROVIDER, CB_SETTINGS_MODEL, CB_SETTINGS_TEST,
    CB_SETTINGS_BACK, CB_PROVIDER_OR, CB_PROVIDER_FA,
)
from bot.keyboards.model_browser import (
    model_filter_keyboard, model_page_keyboard, model_page_text,
)
from config.settings import get_settings, save_bot_config
from agent.state import agent_state
from providers import build_provider

router = Router()


# ════════════════════════════════════════════════════
# FSM STATES
# ════════════════════════════════════════════════════

class SettingsStates(StatesGroup):
    waiting_model_input = State()


# ════════════════════════════════════════════════════
# GUARD HELPER
# ════════════════════════════════════════════════════

async def _agent_active_notice(query: CallbackQuery) -> bool:
    """
    If the agent is running, show a warning and return True (caller should abort).
    Returns False if settings changes are safe to apply.
    """
    if agent_state.is_active:
        await query.answer(
            "Агент сейчас активен. Дождись завершения задачи.",
            show_alert=True,
        )
        return True
    return False


# ════════════════════════════════════════════════════
# SETTINGS MAIN SCREEN
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SETTINGS)
async def cb_settings(query: CallbackQuery) -> None:
    settings = get_settings()
    locked   = " [АГЕНТ АКТИВЕН]" if agent_state.is_active else ""
    text = (
        f"<b>Настройки{locked}</b>\n\n"
        f"Провайдер: <code>{settings.bot.active_provider}</code>\n"
        f"Модель: <code>{settings.bot.active_model or 'по умолчанию'}</code>"
    )
    await query.message.edit_text(
        text,
        parse_mode   = "HTML",
        reply_markup = settings_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_SETTINGS_BACK)
async def cb_settings_back(query: CallbackQuery) -> None:
    await cb_settings(query)


# ════════════════════════════════════════════════════
# PROVIDER SELECTION  [GUARDED]
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SETTINGS_PROVIDER)
async def cb_provider_menu(query: CallbackQuery) -> None:
    if await _agent_active_notice(query):
        return
    settings = get_settings()
    await query.message.edit_text(
        "<b>Выбор провайдера</b>\n\nВыбери LLM провайдера:",
        parse_mode   = "HTML",
        reply_markup = provider_select_keyboard(settings.bot.active_provider),
    )
    await query.answer()


@router.callback_query(F.data.in_({CB_PROVIDER_OR, CB_PROVIDER_FA}))
async def cb_select_provider(query: CallbackQuery) -> None:
    if await _agent_active_notice(query):
        return
    settings  = get_settings()
    chosen    = "openrouter" if query.data == CB_PROVIDER_OR else "favoriteapi"
    settings.bot.active_provider = chosen
    settings.bot.active_model    = None   # reset model when switching provider
    save_bot_config(settings.bot)

    await query.message.edit_text(
        f"<b>Провайдер изменён:</b> <code>{chosen}</code>\n\nМодель сброшена на умолчание.",
        parse_mode   = "HTML",
        reply_markup = provider_select_keyboard(chosen),
    )
    await query.answer(f"Активен: {chosen}")


# ════════════════════════════════════════════════════
# MODEL BROWSER  [GUARDED]
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SETTINGS_MODEL)
async def cb_model_menu(query: CallbackQuery) -> None:
    if await _agent_active_notice(query):
        return
    settings = get_settings()
    if settings.bot.active_provider != "openrouter":
        models = await _get_models(settings)
        text   = "<b>Модели FavoriteAPI</b>\n\nВыбери модель:"
        rows   = [
            [InlineKeyboardButton(
                text          = f"{'* ' if m.id == settings.bot.active_model else ''}{m.name}",
                callback_data = f"models:select:{m.id}",
            )]
            for m in models
        ]
        rows.append([InlineKeyboardButton(text="Назад", callback_data=CB_SETTINGS_BACK)])
        await query.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
    else:
        await query.message.edit_text(
            "<b>Выбор модели</b>\n\nОтфильтруй по типу:",
            parse_mode   = "HTML",
            reply_markup = model_filter_keyboard(),
        )
    await query.answer()


@router.callback_query(F.data.startswith("models:free:") | F.data.startswith("models:paid:"))
async def cb_model_page(query: CallbackQuery) -> None:
    if await _agent_active_notice(query):
        return
    parts    = query.data.split(":")   # ["models", "free"|"paid", page_num]
    tier     = parts[1]
    page     = int(parts[2])
    settings = get_settings()

    models   = await _get_models(settings)
    filtered = [m for m in models if (m.is_free if tier == "free" else not m.is_free)]
    text     = model_page_text(tier, page, len(filtered))
    kb       = model_page_keyboard(models, tier, page, active_model=settings.bot.active_model)

    await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await query.answer()


@router.callback_query(F.data.startswith("models:select:"))
async def cb_model_select(query: CallbackQuery) -> None:
    if await _agent_active_notice(query):
        return
    model_id = query.data[len("models:select:"):]
    settings = get_settings()
    settings.bot.active_model = model_id
    save_bot_config(settings.bot)

    await query.message.edit_text(
        f"<b>Модель выбрана:</b>\n<code>{model_id}</code>",
        parse_mode   = "HTML",
        reply_markup = settings_keyboard(),
    )
    await query.answer("Модель сохранена")


@router.callback_query(F.data == "models:manual")
async def cb_model_manual(query: CallbackQuery, state: FSMContext) -> None:
    if await _agent_active_notice(query):
        return
    await state.set_state(SettingsStates.waiting_model_input)
    await query.message.edit_text(
        "<b>Ручной ввод модели</b>\n\n"
        "Введи ID модели (например: <code>deepseek/deepseek-v4-flash</code>)\n\n"
        "<i>Список моделей: openrouter.ai/models</i>",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data=CB_SETTINGS_BACK)]
        ]),
    )
    await query.answer()


@router.message(SettingsStates.waiting_model_input)
async def process_model_input(message: Message, state: FSMContext) -> None:
    model_id = message.text.strip()
    settings = get_settings()
    settings.bot.active_model = model_id
    save_bot_config(settings.bot)
    await state.clear()
    await message.answer(
        f"<b>Модель установлена:</b>\n<code>{model_id}</code>",
        parse_mode   = "HTML",
        reply_markup = settings_keyboard(),
    )


@router.callback_query(F.data == "models:noop")
async def cb_noop(query: CallbackQuery) -> None:
    await query.answer()   # page indicator — ignore


# ════════════════════════════════════════════════════
# CONNECTION TEST
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SETTINGS_TEST)
async def cb_test_connection(query: CallbackQuery) -> None:
    await query.message.edit_text("Проверяю подключение...", parse_mode="HTML")
    settings = get_settings()

    try:
        provider = build_provider(settings)
        ok       = await provider.health_check()
        status   = "Подключение успешно" if ok else "Не удалось подключиться"
    except ValueError as e:
        status = f"Ошибка конфигурации: {e}"
    except Exception as e:
        status = f"Ошибка: {e}"

    await query.message.edit_text(
        f"<b>Тест подключения</b>\n\n{status}\n\nПровайдер: <code>{settings.bot.active_provider}</code>",
        parse_mode   = "HTML",
        reply_markup = settings_keyboard(),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# INTERNAL HELPERS
# ════════════════════════════════════════════════════

async def _get_models(settings):
    """Fetch model list from the active provider (may hit API)."""
    try:
        p = build_provider(settings)
        return await p.get_models()
    except Exception:
        return []
