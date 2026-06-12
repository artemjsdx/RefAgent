"""
reply_keyboard.py — Reply-клавиатуры для RefAgent бота.

Меняются в зависимости от FSM-состояния чата:
  idle_keyboard()    — dialog / stopped (ждём задачу)
  plan_keyboard()    — awaiting_run (показан план)
  running_keyboard() — running (агент работает)
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


# ════════════════════════════════════════════════════
# ТЕКСТ КНОПОК (константы для reply_handler)
# ════════════════════════════════════════════════════

BTN_WRITE_TASK  = "📝 Написать задачу"
BTN_STATS       = "📊 Статистика"

BTN_STOP        = "⛔ Остановить"
BTN_STOP_WRITE  = "✏️ Стоп + написать"

BTN_PLAN_RUN    = "✅ Запустить план"
BTN_PLAN_EDIT   = "✏️ Изменить"
BTN_PLAN_CANCEL = "❌ Отмена"


# ════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ════════════════════════════════════════════════════

def idle_keyboard() -> ReplyKeyboardMarkup:
    """Состояние dialog / stopped — ждём задачу."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_WRITE_TASK), KeyboardButton(text=BTN_STATS)],
        ],
        resize_keyboard  = True,
        one_time_keyboard= False,
    )


def running_keyboard() -> ReplyKeyboardMarkup:
    """Состояние running — агент выполняет задачу."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STOP), KeyboardButton(text=BTN_STOP_WRITE)],
        ],
        resize_keyboard  = True,
        one_time_keyboard= False,
    )


def plan_keyboard() -> ReplyKeyboardMarkup:
    """Состояние awaiting_run — план показан, ждём подтверждения."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_PLAN_RUN)],
            [KeyboardButton(text=BTN_PLAN_EDIT), KeyboardButton(text=BTN_PLAN_CANCEL)],
        ],
        resize_keyboard  = True,
        one_time_keyboard= True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """Убрать reply-клавиатуру (редко нужно)."""
    return ReplyKeyboardRemove()
