"""
sessions.py — Обработчики для управления Telegram-сессиями в боте.

Поддерживает:
  - Приём .zip архивов (безопасная распаковка, Zip Slip защита)
  - Приём .session файлов через FSM: бот запрашивает api_id и api_hash
  - Прогресс загрузки через аниматор
  - Список аккаунтов с пагинацией
  - Детальный просмотр и управление аккаунтом
  - Назначение проводника (один на всю систему)
"""

import json
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.main_menu import CB_SESSIONS, back_to_main_keyboard
from bot.keyboards.session_menu import (
    sessions_main_keyboard, accounts_page_keyboard,
    account_detail_keyboard, account_detail_text, confirm_delete_keyboard,
    ACCOUNTS_PER_PAGE, CB_SESS_UPLOAD, CB_SESS_BACK, CB_BACK_MAIN,
)
from bot.ui.animator import Animator
from bot.file_buffer import push_file, FileAttachment
from config.constants import SESSIONS_DIR, UPLOADS_DIR
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
# FSM СОСТОЯНИЯ для загрузки одиночного .session файла
# ════════════════════════════════════════════════════

class SessionUpload(StatesGroup):
    waiting_api_id   = State()
    waiting_api_hash = State()


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


# ════════════════════════════════════════════════════
# СПИСОК АККАУНТОВ (пагинация)
# ════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("sess:list:"))
async def cb_accounts_list(query: CallbackQuery) -> None:
    page     = int(query.data.split(":")[-1])
    accounts = await get_all_accounts()

    if not accounts:
        await query.message.edit_text(
            "Аккаунты не загружены.\n\nОтправь .zip архив или .session файл.",
            reply_markup=back_to_main_keyboard(),
        )
        await query.answer()
        return

    total       = len(accounts)
    total_pages = max(1, (total + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    start       = page * ACCOUNTS_PER_PAGE
    page_items  = accounts[start : start + ACCOUNTS_PER_PAGE]

    text = f"<b>Аккаунты</b>  ({total} всего, стр. {page + 1}/{total_pages})"
    await query.message.edit_text(
        text,
        parse_mode   = "HTML",
        reply_markup = accounts_page_keyboard(page_items, page, total),
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
    if not acc:
        await query.answer("Аккаунт не найден", show_alert=True)
        return
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
# ЗАГРУЗКА ФАЙЛОВ — подсказка
# ════════════════════════════════════════════════════

@router.callback_query(F.data == CB_SESS_UPLOAD)
async def cb_upload_prompt(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "<b>Загрузка сессий</b>\n\n"
        "Отправь мне файл:\n\n"
        "📦 <b>.zip архив</b> — может содержать несколько пар <code>.session + .json</code>\n"
        "   (каждый .json должен иметь поля <code>app_id</code> и <code>app_hash</code>)\n\n"
        "📄 <b>.session файл</b> — бот запросит <code>api_id</code> и <code>api_hash</code> интерактивно\n\n"
        "<b>⚠️ Важно:</b> каждый аккаунт обязан иметь <b>уникальный</b> api_id.\n"
        "Один api_id на несколько аккаунтов = массовая заморозка.",
        parse_mode   = "HTML",
        reply_markup = back_to_main_keyboard(),
    )
    await query.answer()


# ════════════════════════════════════════════════════
# ПРИЁМ ДОКУМЕНТОВ (.zip и .session)
# ════════════════════════════════════════════════════

@router.message(F.document)
async def handle_document(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработать входящий документ.

    .zip / .session → загрузка сессий в базу (только при активном чате).
    Всё остальное   → буферизуется в file_buffer для следующей задачи агенту.

    Файлы изолированы по чату: active_chat_id — ключ sandbox.
    """
    doc: Document = message.document
    fname = doc.file_name or ""

    # active_chat_id — ключ sandbox (из FSM данных активного чата)
    fsm_data       = await state.get_data()
    active_chat_id = fsm_data.get("active_chat_id")

    tg_chat_id = message.chat.id   # только для аниматора

    # ── Нессионные файлы → file_buffer для агента ─────────
    if not (fname.endswith(".zip") or fname.endswith(".session")):
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        attachment = FileAttachment(
            file_id   = doc.file_id,
            file_name = fname,
            mime_type = doc.mime_type or "application/octet-stream",
            size      = doc.file_size or 0,
        )
        push_file(active_chat_id, attachment)   # sandbox по active_chat_id
        size_kb = (doc.file_size or 0) // 1024
        await message.reply(
            f"📎 <code>{fname}</code> ({size_kb} КБ) прикреплён к следующей задаче.\n"
            "Теперь напиши что нужно сделать.",
            parse_mode="HTML",
        )
        return

    # ── Сессионные файлы требуют активного чата ──────────
    if not active_chat_id:
        await message.reply(
            "❌ <b>Чат не выбран.</b>\n\n"
            "Создай или открой чат, затем загрузи сессии — "
            "они будут привязаны именно к нему.",
            parse_mode="HTML",
        )
        return

    # Директория сессий изолирована по чату: data/sessions/chat_{id}/
    chat_sessions_dir = SESSIONS_DIR / f"chat_{active_chat_id}"
    chat_sessions_dir.mkdir(parents=True, exist_ok=True)
    dest = chat_sessions_dir / fname

    # ── Скачать файл ──────────────────────────────────────
    anim   = _animator
    msg_id = None

    if anim:
        msg_id = await anim.start(tg_chat_id, "saving")

    await bot.download(doc, destination=str(dest))

    # ── ZIP: обработать сразу ─────────────────────────────
    if fname.endswith(".zip"):
        results = await extract_and_load_zip(dest, chat_id=active_chat_id)
        report  = format_load_report(results)
        if anim and msg_id:
            await anim.finalize(tg_chat_id, msg_id, report)
        else:
            await message.answer(report, parse_mode="HTML")
        return

    # ── .session: проверить sidecar JSON ─────────────────
    # Если рядом нет .json — запустить FSM для ручного ввода
    sidecar_path = dest.with_suffix(".json")
    if sidecar_path.exists():
        # Sidecar уже есть — грузим напрямую
        results = [await load_session_file(dest, chat_id=active_chat_id)]
        report  = format_load_report(results)
        if anim and msg_id:
            await anim.finalize(tg_chat_id, msg_id, report)
        else:
            await message.answer(report, parse_mode="HTML")
        return

    # Sidecar не найден — начинаем FSM
    if anim and msg_id:
        await anim.finalize(tg_chat_id, msg_id, f"📄 Файл <code>{fname}</code> получен.")

    await state.set_state(SessionUpload.waiting_api_id)
    await state.update_data(session_path=str(dest))
    # active_chat_id уже в state data — он сохранится через update_data

    await message.answer(
        f"Файл <code>{fname}</code> сохранён.\n\n"
        "Введи <b>api_id</b> для этого аккаунта (целое число).\n"
        "<i>Получить можно на my.telegram.org → App configuration → App api_id</i>",
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════
# FSM ШАГ 1: ввод api_id
# ════════════════════════════════════════════════════

@router.message(SessionUpload.waiting_api_id)
async def fsm_receive_api_id(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()

    try:
        api_id = int(text)
        if api_id <= 0:
            raise ValueError
    except ValueError:
        await message.reply(
            "❌ api_id должен быть положительным целым числом.\n"
            "Пример: <code>12345678</code>\n\nПопробуй ещё раз:",
            parse_mode="HTML",
        )
        return

    await state.update_data(api_id=api_id)
    await state.set_state(SessionUpload.waiting_api_hash)
    await message.answer(
        f"api_id <code>{api_id}</code> принят.\n\n"
        "Теперь введи <b>api_hash</b> (строка из 32 символов).\n"
        "<i>Там же: my.telegram.org → App configuration → App api_hash</i>",
        parse_mode="HTML",
    )


# ════════════════════════════════════════════════════
# FSM ШАГ 2: ввод api_hash → создание sidecar + загрузка
# ════════════════════════════════════════════════════

@router.message(SessionUpload.waiting_api_hash)
async def fsm_receive_api_hash(message: Message, state: FSMContext) -> None:
    api_hash = (message.text or "").strip()

    if not api_hash or len(api_hash) < 8:
        await message.reply(
            "❌ api_hash слишком короткий. Обычно это строка из 32 символов.\n"
            "Пример: <code>a1b2c3d4e5f6...</code>\n\nПопробуй ещё раз:",
            parse_mode="HTML",
        )
        return

    data           = await state.get_data()
    api_id         = data["api_id"]
    session_path   = Path(data["session_path"])
    active_chat_id = data.get("active_chat_id")

    # Создать sidecar JSON
    sidecar = session_path.with_suffix(".json")
    sidecar.write_text(
        json.dumps({"app_id": api_id, "app_hash": api_hash}, ensure_ascii=False),
        encoding="utf-8",
    )

    # Восстановить dialog-состояние с active_chat_id (не clear — чтобы не потерять чат)
    from bot.handlers.chat import ChatStates
    await state.set_state(ChatStates.dialog)
    await state.set_data({"active_chat_id": active_chat_id})

    # Загрузить сессию
    anim       = _animator
    msg_id     = None
    tg_chat_id = message.chat.id

    if anim:
        msg_id = await anim.start(tg_chat_id, "saving")

    results = [await load_session_file(session_path, chat_id=active_chat_id)]
    report  = format_load_report(results)

    if anim and msg_id:
        await anim.finalize(tg_chat_id, msg_id, report)
    else:
        await message.answer(report, parse_mode="HTML")


# ════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ
# ════════════════════════════════════════════════════

@router.callback_query(F.data == "sess:noop")
async def cb_noop(query: CallbackQuery) -> None:
    await query.answer()
