"""
main_menu.py — Main menu and navigation keyboards for RefAgent bot.

Navigation model: every sub-screen has a Back button that returns to its parent.
Callback data format: "menu:<screen_name>"
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ════════════════════════════════════════════════════
# CALLBACK DATA CONSTANTS
# ════════════════════════════════════════════════════

CB_CHAT       = "menu:chat"
CB_SESSIONS   = "menu:sessions"
CB_SETTINGS   = "menu:settings"
CB_STATS      = "menu:stats"
CB_ABOUT      = "menu:about"
CB_BACK_MAIN  = "menu:back_main"

CB_SETTINGS_PROVIDER = "settings:provider"
CB_SETTINGS_MODEL    = "settings:model"
CB_SETTINGS_TEST     = "settings:test"
CB_SETTINGS_BACK     = "settings:back"

CB_PROVIDER_OR       = "provider:openrouter"
CB_PROVIDER_FA       = "provider:favoriteapi"
CB_PROVIDER_BACK     = "provider:back"


# ════════════════════════════════════════════════════
# MAIN MENU
# ════════════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Чат с агентом",  callback_data=CB_CHAT)],
        [InlineKeyboardButton(text="Сессии",         callback_data=CB_SESSIONS)],
        [InlineKeyboardButton(text="Настройки",      callback_data=CB_SETTINGS)],
        [InlineKeyboardButton(text="Статистика",     callback_data=CB_STATS)],
        [InlineKeyboardButton(text="О проекте",      callback_data=CB_ABOUT)],
    ])


# ════════════════════════════════════════════════════
# SETTINGS MENU
# ════════════════════════════════════════════════════

def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="LLM Провайдер",      callback_data=CB_SETTINGS_PROVIDER)],
        [InlineKeyboardButton(text="Выбор модели",        callback_data=CB_SETTINGS_MODEL)],
        [InlineKeyboardButton(text="Тест подключения",   callback_data=CB_SETTINGS_TEST)],
        [InlineKeyboardButton(text="Назад",              callback_data=CB_BACK_MAIN)],
    ])


def provider_select_keyboard(active: str) -> InlineKeyboardMarkup:
    """active: 'openrouter' | 'favoriteapi'"""
    or_mark = " (активен)" if active == "openrouter"  else ""
    fa_mark = " (активен)" if active == "favoriteapi" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"OpenRouter{or_mark}",  callback_data=CB_PROVIDER_OR)],
        [InlineKeyboardButton(text=f"FavoriteAPI{fa_mark}", callback_data=CB_PROVIDER_FA)],
        [InlineKeyboardButton(text="Назад",                 callback_data=CB_SETTINGS_BACK)],
    ])


# ════════════════════════════════════════════════════
# TASK CONTROL (shown during agent execution)
# ════════════════════════════════════════════════════

CB_STOP        = "task:stop"
CB_STOP_WRITE  = "task:stop_write"


def task_controls_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Остановить",      callback_data=CB_STOP),
            InlineKeyboardButton(text="Стоп + написать", callback_data=CB_STOP_WRITE),
        ]
    ])


# ════════════════════════════════════════════════════
# PLAN CONFIRMATION
# ════════════════════════════════════════════════════

CB_PLAN_RUN    = "plan:run"
CB_PLAN_EDIT   = "plan:edit"
CB_PLAN_CANCEL = "plan:cancel"


def plan_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Запустить",       callback_data=CB_PLAN_RUN),
            InlineKeyboardButton(text="Изменить план",   callback_data=CB_PLAN_EDIT),
        ],
        [InlineKeyboardButton(text="Отмена",             callback_data=CB_PLAN_CANCEL)],
    ])


# ════════════════════════════════════════════════════
# GENERIC BACK BUTTON
# ════════════════════════════════════════════════════

def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=CB_BACK_MAIN)]
    ])
