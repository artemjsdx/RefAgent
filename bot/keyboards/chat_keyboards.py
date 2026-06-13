"""
chat_keyboards.py — Клавиатуры для создания и управления чатами.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from tools.chat_db import ChatRecord, PROVIDER_LABELS, PROVIDER_EMOJIS, fmt_ts


# ════════════════════════════════════════════════════
# CALLBACK CONSTANTS
# ════════════════════════════════════════════════════

CB_NEW_CHAT       = "chat:new"
CB_CHAT_LIST      = "chat:list"
CB_CHAT_OPEN      = "chat:open:"         # + chat_id
CB_CHAT_DELETE    = "chat:delete:"       # + chat_id
CB_CHAT_CONFIRM   = "chat:confirm_del:"  # + chat_id
CB_CHAT_BACK_LIST = "chat:back_list"
CB_CHAT_EDIT      = "chat:edit:"         # + chat_id

CB_PROV_OR  = "newchat:prov:openrouter"
CB_PROV_FA  = "newchat:prov:favoriteapi"
CB_PROV_BAI = "newchat:prov:bai"
CB_SKIP_MODEL = "newchat:skip_model"
CB_SKIP_URL   = "newchat:skip_url"


# ════════════════════════════════════════════════════
# PROVIDER PICKER (шаг 2 создания чата)
# ════════════════════════════════════════════════════

def provider_picker_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔀 OpenRouter",   callback_data=CB_PROV_OR)],
        [InlineKeyboardButton(text="⭐ FavoriteAPI",  callback_data=CB_PROV_FA)],
        [InlineKeyboardButton(text="💡 b.ai (бесплатно 500K)", callback_data=CB_PROV_BAI)],
        [InlineKeyboardButton(text="❌ Отмена",       callback_data="menu:back_main")],
    ])


# ════════════════════════════════════════════════════
# SKIP MODEL (шаг 4 создания чата)
# ════════════════════════════════════════════════════

def skip_model_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить (по умолчанию)", callback_data=CB_SKIP_MODEL)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:back_main")],
    ])


def skip_url_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:back_main")],
    ])


# ════════════════════════════════════════════════════
# CHAT LIST
# ════════════════════════════════════════════════════

def chat_list_keyboard(chats: list[ChatRecord]) -> InlineKeyboardMarkup:
    rows = []
    for chat in chats:
        prov_emoji = PROVIDER_EMOJIS.get(chat.provider, "🤖")
        ts = fmt_ts(chat.last_used or chat.created_at)
        label = f"💬 {chat.name}  {prov_emoji} · {ts}"
        rows.append([InlineKeyboardButton(
            text          = label,
            callback_data = f"{CB_CHAT_OPEN}{chat.id}",
        )])

    rows.append([InlineKeyboardButton(text="➕ Новый чат", callback_data=CB_NEW_CHAT)])
    rows.append([InlineKeyboardButton(text="◀️ Назад",    callback_data="menu:back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════
# CHAT DETAIL
# ════════════════════════════════════════════════════

def chat_detail_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Открыть",     callback_data=f"{CB_CHAT_OPEN}{chat_id}:enter"),
            InlineKeyboardButton(text="✏️ Изменить",    callback_data=f"{CB_CHAT_EDIT}{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить",     callback_data=f"{CB_CHAT_DELETE}{chat_id}"),
            InlineKeyboardButton(text="◀️ К списку",   callback_data=CB_CHAT_BACK_LIST),
        ],
    ])


def confirm_delete_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить",   callback_data=f"{CB_CHAT_CONFIRM}{chat_id}"),
            InlineKeyboardButton(text="❌ Отмена",        callback_data=f"{CB_CHAT_OPEN}{chat_id}"),
        ],
    ])
