"""
start.py — /start хендлер и роутинг главного меню.

CB_SESSIONS теперь обрабатывается в bot/handlers/sessions.py.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from bot.keyboards.main_menu import (
    main_menu_keyboard, back_to_main_keyboard,
    CB_CHAT, CB_STATS, CB_ABOUT, CB_BACK_MAIN,
)
from config.constants import BOT_NAME, BOT_VERSION
from config.settings import get_settings

router = Router()


# ════════════════════════════════════════════════════
# /start — ПРИВЕТСТВИЕ
# ════════════════════════════════════════════════════

WELCOME_TEXT = """
<b>{name} v{version}</b>

Автономный агент для реферальных программ Telegram.

<b>Настрой перед запуском:</b>

  1. <b>LLM Провайдер</b>
     Настройки → LLM Провайдер
     Нужен API ключ OpenRouter или FavoriteAPI

  2. <b>Сессии аккаунтов</b>
     Сессии → Загрузить сессии
     Отправь .zip или .session файлы

  3. <b>Проводник</b>
     Сессии → выбери аккаунт → Назначить проводником
     Прогретый аккаунт для обхода DM-ограничений

<i>Нажми "Чат с агентом" чтобы поставить задачу.</i>
""".strip()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT.format(name=BOT_NAME, version=BOT_VERSION),
        parse_mode   = "HTML",
        reply_markup = main_menu_keyboard(),
    )


# ════════════════════════════════════════════════════
# НАВИГАЦИЯ ГЛАВНОГО МЕНЮ
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_BACK_MAIN)
async def cb_back_main(query: CallbackQuery) -> None:
    await query.message.edit_text(
        WELCOME_TEXT.format(name=BOT_NAME, version=BOT_VERSION),
        parse_mode   = "HTML",
        reply_markup = main_menu_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_CHAT)
async def cb_chat(query: CallbackQuery) -> None:
    settings = get_settings()
    provider = settings.bot.active_provider
    model    = settings.bot.active_model or "по умолчанию"
    await query.message.edit_text(
        f"<b>Чат с агентом</b>\n\n"
        f"Провайдер: <code>{provider}</code>\n"
        f"Модель: <code>{model}</code>\n\n"
        f"Напиши задачу — реф ссылку, условия зачисления, количество аккаунтов.\n"
        f"Агент составит план и покажет его перед запуском.\n\n"
        f"<i>Требуется настроить провайдер LLM.</i>",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_STATS)
async def cb_stats(query: CallbackQuery) -> None:
    from tools.db import get_all_accounts
    accounts = await get_all_accounts()
    total    = len(accounts)
    active   = sum(1 for a in accounts if a.status == "ACTIVE")
    frozen   = sum(1 for a in accounts if a.status == "FROZEN")
    cond     = sum(1 for a in accounts if a.is_conductor)
    await query.message.edit_text(
        "<b>Статистика</b>\n\n"
        "<pre>"
        f"{'Задач выполнено':<22} 0\n"
        f"{'Рефов засчитано':<22} 0\n"
        f"{'Аккаунтов в пуле':<22} {total}\n"
        f"{'  активных':<22} {active}\n"
        f"{'  замороженных':<22} {frozen}\n"
        f"{'  проводников':<22} {cond}\n"
        "</pre>",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_ABOUT)
async def cb_about(query: CallbackQuery) -> None:
    await query.message.edit_text(
        f"<b>{BOT_NAME} v{BOT_VERSION}</b>\n\n"
        "Открытый инструмент автоматизации реферальных программ Telegram.\n\n"
        "<b>GitHub:</b> github.com/artemjsdx/RefAgent\n\n"
        "<b>Стек:</b> Python · aiogram 3 · Telethon · OpenRouter / FavoriteAPI\n\n"
        "<b>Принципы:</b>\n"
        "— Уникальный api_id/api_hash на каждый аккаунт\n"
        "— Conductor pattern для обхода DM-ограничений\n"
        "— Библиотека знаний об ошибках\n"
        "— Plan before action",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()
