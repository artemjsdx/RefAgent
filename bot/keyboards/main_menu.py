"""
main_menu.py — Главное меню и навигационные клавиатуры RefAgent.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ════════════════════════════════════════════════════
# CALLBACK CONSTANTS
# ════════════════════════════════════════════════════

CB_CHAT       = "menu:chat"          # устаревший — оставлен для совместимости
CB_CHAT_LIST  = "chat:list"          # список чатов
CB_NEW_CHAT   = "chat:new"           # новый чат
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
CB_PROVIDER_BAI      = "provider:bai"
CB_PROVIDER_BACK     = "provider:back"


# ════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ════════════════════════════════════════════════════

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Новый чат",   callback_data=CB_NEW_CHAT),
            InlineKeyboardButton(text="💬 Мои чаты",    callback_data=CB_CHAT_LIST),
        ],
        [InlineKeyboardButton(text="🗄️ Сессии",         callback_data=CB_SESSIONS)],
        [
            InlineKeyboardButton(text="📊 Статистика",  callback_data=CB_STATS),
            InlineKeyboardButton(text="ℹ️ О проекте",   callback_data=CB_ABOUT),
        ],
    ])


# ════════════════════════════════════════════════════
# TASK CONTROL (during agent execution)
# ════════════════════════════════════════════════════

CB_STOP        = "task:stop"
CB_STOP_WRITE  = "task:stop_write"


def task_controls_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⛔ Остановить",        callback_data=CB_STOP),
            InlineKeyboardButton(text="✏️ Стоп + написать",  callback_data=CB_STOP_WRITE),
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
            InlineKeyboardButton(text="🚀 Запустить",       callback_data=CB_PLAN_RUN),
            InlineKeyboardButton(text="✏️ Изменить план",   callback_data=CB_PLAN_EDIT),
        ],
        [InlineKeyboardButton(text="❌ Отмена",             callback_data=CB_PLAN_CANCEL)],
    ])


# ════════════════════════════════════════════════════
# GENERIC BACK BUTTON
# ════════════════════════════════════════════════════

def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data=CB_BACK_MAIN)]
    ])


# ════════════════════════════════════════════════════
# SETTINGS (упрощённое — только глобальные параметры)
# ════════════════════════════════════════════════════

def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Тест подключения", callback_data=CB_SETTINGS_TEST)],
        [InlineKeyboardButton(text="◀️ Назад",            callback_data=CB_BACK_MAIN)],
    ])


def provider_select_keyboard(active: str) -> InlineKeyboardMarkup:
    """active: 'openrouter' | 'favoriteapi' | 'bai'"""
    mark = lambda p: " ✓" if active == p else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔀 OpenRouter{mark('openrouter')}",       callback_data=CB_PROVIDER_OR)],
        [InlineKeyboardButton(text=f"⭐ FavoriteAPI{mark('favoriteapi')}",      callback_data=CB_PROVIDER_FA)],
        [InlineKeyboardButton(text=f"💡 b.ai (500K бесплатно){mark('bai')}",   callback_data=CB_PROVIDER_BAI)],
        [InlineKeyboardButton(text="◀️ Назад",                                  callback_data=CB_SETTINGS_BACK)],
    ])
