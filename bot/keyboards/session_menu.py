"""
session_menu.py — Клавиатуры для управления сессиями аккаунтов.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tools.db import AccountRecord

ACCOUNTS_PER_PAGE = 8

# ── Callback константы ──
CB_SESSIONS_LIST      = "sess:list:0"
CB_SESS_UPLOAD        = "sess:upload"
CB_SESS_BACK          = "sess:back"
CB_BACK_MAIN          = "menu:back_main"


def sessions_main_keyboard(total: int, conductor_set: bool) -> InlineKeyboardMarkup:
    cond_label = "Проводник: назначен" if conductor_set else "Проводник: не назначен"
    rows = []
    if total > 0:
        rows.append([InlineKeyboardButton(text=f"Аккаунты ({total})", callback_data="sess:list:0")])
    rows.append([InlineKeyboardButton(text="Загрузить сессии (.zip / .session)", callback_data=CB_SESS_UPLOAD)])
    rows.append([InlineKeyboardButton(text=cond_label, callback_data="sess:list:0")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=CB_BACK_MAIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def accounts_page_keyboard(
    accounts: list[AccountRecord],
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + ACCOUNTS_PER_PAGE - 1) // ACCOUNTS_PER_PAGE)
    rows = []

    for acc in accounts:
        label = _account_label(acc)
        rows.append([InlineKeyboardButton(
            text          = label,
            callback_data = f"sess:detail:{acc.id}",
        )])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=f"sess:list:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="sess:noop"))
    if (page + 1) * ACCOUNTS_PER_PAGE < total:
        nav.append(InlineKeyboardButton(text="Вперёд", callback_data=f"sess:list:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="Загрузить ещё", callback_data=CB_SESS_UPLOAD)])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=CB_SESS_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_detail_keyboard(acc: AccountRecord) -> InlineKeyboardMarkup:
    rows = []
    if acc.is_conductor:
        rows.append([InlineKeyboardButton(text="Снять роль проводника", callback_data=f"sess:unconductor:{acc.id}")])
    else:
        rows.append([InlineKeyboardButton(text="Назначить проводником", callback_data=f"sess:conductor:{acc.id}")])

    status_next = "FROZEN" if acc.status == "ACTIVE" else "ACTIVE"
    status_label = "Заморозить" if acc.status == "ACTIVE" else "Разморозить"
    rows.append([InlineKeyboardButton(text=status_label, callback_data=f"sess:setstatus:{acc.id}:{status_next}")])
    rows.append([InlineKeyboardButton(text="Удалить из БД", callback_data=f"sess:delete:{acc.id}")])
    rows.append([InlineKeyboardButton(text="Назад к списку", callback_data="sess:list:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_keyboard(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, удалить", callback_data=f"sess:confirmdelete:{account_id}"),
            InlineKeyboardButton(text="Отмена",       callback_data=f"sess:detail:{account_id}"),
        ]
    ])


# ── Хелперы ──

def _account_label(acc: AccountRecord) -> str:
    icons = {
        "ACTIVE":  "",
        "FROZEN":  "[замор] ",
        "BANNED":  "[бан] ",
        "UNKNOWN": "[?] ",
    }
    prefix = "[П] " if acc.is_conductor else ""
    status = icons.get(acc.status, "")
    uid_str = f" uid:{acc.uid}" if acc.uid else ""
    cat     = f" ({acc.uid_category})" if acc.uid_category != "UNKNOWN" else ""
    return f"{prefix}{status}{acc.phone}{uid_str}{cat}"


def account_detail_text(acc: AccountRecord) -> str:
    lines = [
        f"<b>Аккаунт: {acc.phone}</b>",
        "",
        f"UID: <code>{acc.uid or 'неизвестен'}</code>",
        f"Категория: <code>{acc.uid_category}</code>",
        f"Формат: <code>{acc.format}</code>",
        f"Статус: <code>{acc.status}</code>",
        f"api_id: <code>{acc.api_id}</code>",
        f"Проводник: {'Да' if acc.is_conductor else 'Нет'}",
        f"Добавлен: {acc.added_at or '—'}",
        f"Последнее использование: {acc.last_used or '—'}",
        "",
        f"Файл: <code>{acc.session_path}</code>",
    ]
    return "\n".join(lines)
