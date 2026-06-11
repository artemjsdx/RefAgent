"""
sessions.py — Обработчики для управления Telegram-сессиями в боте.

Поддерживает:
  - Приём .zip и .session файлов от пользователя
  - Прогресс загрузки через аниматор
  - Список аккаунтов с пагинацией
  - Детальный просмотр и управление аккаунтом
  - Назначение проводника (один на всю систему)
"""

import os
import tempfile
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Document

from bot.keyboards.main_menu import CB_SESSIONS, back_to_main_keyboard
from bot.keyboards.session_menu import (
    sessions_main_keyboard, accounts_page_keyboard,
    account_detail_keyboard, account_detail_text, confirm_delete_keyboard,
    ACCOUNTS_PER_PAGE, CB_SESS_UPLOAD, CB_SESS_BACK, CB_BACK_MAIN,
)
from bot.ui.animator import Animator
from config.constants import SESSIONS_DIR
from tools.db import (
    get_all_accounts, get_account, get_conductor,
    set_conductor, update_status, delete_account,
)
from tools.session_tools import (
    extract_and_load_zip, load_session_file, format_load_report,
)

router = Router()
_animator: Animator | None = None


def set_animator(a: Animator) -> None:
    """Внедрить экземпляр Animator (вызывается из refagent.py)."""
    global _animator
    _animator = a


# ════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ СЕССИЙ
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SESSIONS)
async def cb_sessions_main(query: CallbackQuery) -> None:
    accounts  = await get_all_accounts()
    conductor = await get_conductor()
    text = (
        "<b>Сессии аккаунтов</b>\n\n"
        f"Загружено: <b>{len(accounts)}</b>\n"
        f"Проводник: <b>{'назначен' if conductor else 'не назначен'}</b>"
    )
    await query.message.edit_text(
        text,
        parse_mode   = "HTML",
        reply_markup = sessions_main_keyboard(len(accounts), conductor is not None),
    )
    await query.answer()


@router.callback_query(F.data == CB_SESS_BACK)
async def cb_sessions_back(query: CallbackQuery) -> None:
    await cb_sessions_main(query)


# ════════════════════════════════════════════════════
# СПИСОК АККАУНТОВ
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sess:list:"))
async def cb_accounts_list(query: CallbackQuery) -> None:
    page     = int(query.data.split(":")[-1])
    accounts = await get_all_accounts()
    total    = len(accounts)

    if total == 0:
        await query.message.edit_text(
            "<b>Нет загруженных аккаунтов</b>\n\nОтправь .zip или .session файл сюда в чат.",
            parse_mode   = "HTML",
            reply_markup = back_to_main_keyboard(),
        )
        await query.answer()
        return

    start    = page * ACCOUNTS_PER_PAGE
    page_acc = accounts[start : start + ACCOUNTS_PER_PAGE]
    text     = f"<b>Аккаунты</b> — страница {page + 1}, всего {total}"

    await query.message.edit_text(
        text,
        parse_mode   = "HTML",
        reply_markup = accounts_page_keyboard(page_acc, page, total),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# ДЕТАЛИ АККАУНТА
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sess:detail:"))
async def cb_account_detail(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[-1])
    acc        = await get_account(account_id)
    if not acc:
        await query.answer("Аккаунт не найден", show_alert=True)
        return
    await query.message.edit_text(
        account_detail_text(acc),
        parse_mode   = "HTML",
        reply_markup = account_detail_keyboard(acc),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# НАЗНАЧЕНИЕ ПРОВОДНИКА
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sess:conductor:"))
async def cb_set_conductor(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[-1])
    await set_conductor(account_id, True)
    acc = await get_account(account_id)
    await query.message.edit_text(
        f"{account_detail_text(acc)}\n\n<b>Назначен проводником.</b>",
        parse_mode   = "HTML",
        reply_markup = account_detail_keyboard(acc),
    )
    await query.answer("Проводник назначен")


@router.callback_query(F.data.startswith("sess:unconductor:"))
async def cb_unset_conductor(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[-1])
    await set_conductor(account_id, False)
    acc = await get_account(account_id)
    await query.message.edit_text(
        account_detail_text(acc),
        parse_mode   = "HTML",
        reply_markup = account_detail_keyboard(acc),
    )
    await query.answer("Роль проводника снята")


# ════════════════════════════════════════════════════
# СМЕНА СТАТУСА
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sess:setstatus:"))
async def cb_set_status(query: CallbackQuery) -> None:
    parts      = query.data.split(":")
    account_id = int(parts[2])
    new_status = parts[3]
    await update_status(account_id, new_status)
    acc = await get_account(account_id)
    await query.message.edit_text(
        account_detail_text(acc),
        parse_mode   = "HTML",
        reply_markup = account_detail_keyboard(acc),
    )
    await query.answer(f"Статус: {new_status}")


# ════════════════════════════════════════════════════
# УДАЛЕНИЕ
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sess:delete:"))
async def cb_delete_confirm(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[-1])
    acc        = await get_account(account_id)
    await query.message.edit_text(
        f"Удалить аккаунт <b>{acc.phone}</b> из базы данных?\n"
        f"<i>Файл сессии на диске не будет удалён.</i>",
        parse_mode   = "HTML",
        reply_markup = confirm_delete_keyboard(account_id),
    )
    await query.answer()


@router.callback_query(F.data.startswith("sess:confirmdelete:"))
async def cb_delete_execute(query: CallbackQuery) -> None:
    account_id = int(query.data.split(":")[-1])
    acc        = await get_account(account_id)
    phone      = acc.phone if acc else str(account_id)
    await delete_account(account_id)
    accounts   = await get_all_accounts()
    await query.message.edit_text(
        f"Аккаунт <b>{phone}</b> удалён из базы.\n\nОсталось аккаунтов: {len(accounts)}",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer("Удалено")


# ════════════════════════════════════════════════════
# ЗАГРУЗКА ФАЙЛОВ (приём документов от пользователя)
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SESS_UPLOAD)
async def cb_upload_prompt(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "<b>Загрузка сессий</b>\n\n"
        "Отправь мне файл:\n"
        "— <b>.zip</b> архив с парами <code>.session + .json</code>\n"
        "— <b>.session</b> файл (рядом должен быть <code>.json</code> с api_id/api_hash)\n\n"
        "<b>Важно:</b> каждый аккаунт должен иметь свой уникальный api_id в .json файле.\n"
        "Один api_id на несколько аккаунтов = массовая заморозка.",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    """Обработать входящий документ: .zip или .session файл."""
    doc: Document = message.document
    fname = doc.file_name or ""

    if not (fname.endswith(".zip") or fname.endswith(".session")):
        await message.reply(
            "Поддерживаются только файлы <b>.zip</b> и <b>.session</b>.\n"
            "Отправь .zip архив или отдельный .session файл с .json рядом.",
            parse_mode="HTML",
        )
        return

    # Анимация загрузки
    anim    = _animator
    msg_id  = None
    chat_id = message.chat.id

    if anim:
        msg_id = await anim.start(chat_id, "saving")

    # Скачать файл
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SESSIONS_DIR / fname
    await bot.download(doc, destination=str(dest))

    # Обработать
    if fname.endswith(".zip"):
        results = await extract_and_load_zip(dest)
    else:
        results = [await load_session_file(dest)]

    report = format_load_report(results)

    if anim and msg_id:
        await anim.finalize(chat_id, msg_id, report)
    else:
        await message.answer(report, parse_mode="HTML")


@router.callback_query(F.data == "sess:noop")
async def cb_noop(query: CallbackQuery) -> None:
    await query.answer()
