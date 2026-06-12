"""
start.py — /start хендлер и навигация главного меню.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from bot.keyboards.main_menu import (
    main_menu_keyboard, back_to_main_keyboard,
    CB_STATS, CB_ABOUT, CB_BACK_MAIN,
)
from config.constants import BOT_NAME, BOT_VERSION

router = Router()


# ════════════════════════════════════════════════════
# /start
# ════════════════════════════════════════════════════

WELCOME_TEXT = (
    "🤖 <b>{name} v{version}</b>\n\n"
    "Автономный агент для реферальных программ Telegram.\n\n"
    "<b>Быстрый старт:</b>\n"
    "  1️⃣  <b>➕ Новый чат</b> — введи название, выбери провайдер и API ключ\n"
    "  2️⃣  <b>🗄️ Сессии</b> — загрузи .zip с аккаунтами\n"
    "  3️⃣  Напиши задачу — агент составит план и спросит подтверждение\n\n"
    "<i>Каждый чат хранит свой API ключ — безопасно для open source.</i>"
)


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


@router.callback_query(F.data == CB_STATS)
async def cb_stats(query: CallbackQuery) -> None:
    from tools.db import get_all_accounts
    from bot.ui.report import get_stats

    accounts   = await get_all_accounts()
    acc_total  = len(accounts)
    active     = sum(1 for a in accounts if a.status == "ACTIVE")
    frozen     = sum(1 for a in accounts if a.status == "FROZEN")
    cond       = sum(1 for a in accounts if a.is_conductor)
    task_stats = await get_stats()

    await query.message.edit_text(
        "📊 <b>Статистика</b>\n\n"
        "<pre>"
        f"{'Задач выполнено':<22} {task_stats['total']}\n"
        f"{'Рефов засчитано':<22} {task_stats['success']}\n"
        f"{'Аккаунтов в пуле':<22} {acc_total}\n"
        f"  {'активных':<20} {active}\n"
        f"  {'замороженных':<20} {frozen}\n"
        f"  {'проводников':<20} {cond}\n"
        "</pre>",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


@router.callback_query(F.data == CB_ABOUT)
async def cb_about(query: CallbackQuery) -> None:
    await query.message.edit_text(
        f"ℹ️ <b>{BOT_NAME} v{BOT_VERSION}</b>\n\n"
        "Открытый инструмент автоматизации реферальных программ Telegram.\n\n"
        "🔗 <b>GitHub:</b> github.com/artemjsdx/RefAgent\n\n"
        "⚙️ <b>Стек:</b>\n"
        "  Python · aiogram 3 · Telethon\n"
        "  OpenRouter / FavoriteAPI / b.ai\n\n"
        "🔒 <b>Принципы:</b>\n"
        "  — Уникальный api_id/api_hash на каждый аккаунт\n"
        "  — Conductor pattern для обхода DM-ограничений\n"
        "  — API ключи хранятся только в твоих чатах\n"
        "  — Plan before action",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()
