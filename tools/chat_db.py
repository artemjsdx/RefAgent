"""
chat_db.py — CRUD для именованных LLM-чатов.

Каждый чат хранит собственный provider, api_key и model.
Ключи пользователя — только в его чатах, не в env и не в config.json.
"""

from __future__ import annotations

import time
import aiosqlite
from dataclasses import dataclass
from typing import Optional

from config.constants import SESSIONS_DB


# ════════════════════════════════════════════════════
# DATA CLASS
# ════════════════════════════════════════════════════

@dataclass
class ChatRecord:
    id:         Optional[int]
    user_id:    int
    name:       str
    provider:   str             # 'openrouter' | 'favoriteapi' | 'bai'
    api_key:    str
    api_url:    Optional[str]   # FavoriteAPI: base URL
    model:      Optional[str]   # None = provider default
    created_at: int
    last_used:  Optional[int]


CHATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    provider   TEXT    NOT NULL,
    api_key    TEXT    NOT NULL,
    api_url    TEXT,
    model      TEXT,
    created_at INTEGER NOT NULL,
    last_used  INTEGER
);
"""


# ════════════════════════════════════════════════════
# INIT
# ════════════════════════════════════════════════════

async def init_chats_table() -> None:
    """Создать таблицу чатов если не существует."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.executescript(CHATS_SCHEMA)
        await db.commit()


# ════════════════════════════════════════════════════
# CRUD
# ════════════════════════════════════════════════════

async def create_chat(
    user_id:  int,
    name:     str,
    provider: str,
    api_key:  str,
    api_url:  Optional[str] = None,
    model:    Optional[str] = None,
) -> ChatRecord:
    """Создать новый чат и вернуть его."""
    now = int(time.time())
    async with aiosqlite.connect(SESSIONS_DB) as db:
        cursor = await db.execute(
            "INSERT INTO chats (user_id, name, provider, api_key, api_url, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, provider, api_key, api_url, model, now),
        )
        await db.commit()
        return ChatRecord(
            id         = cursor.lastrowid,
            user_id    = user_id,
            name       = name,
            provider   = provider,
            api_key    = api_key,
            api_url    = api_url,
            model      = model,
            created_at = now,
            last_used  = None,
        )


async def get_user_chats(user_id: int) -> list[ChatRecord]:
    """Все чаты пользователя, последние используемые первыми."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            "SELECT id, user_id, name, provider, api_key, api_url, model, created_at, last_used "
            "FROM chats WHERE user_id = ? ORDER BY COALESCE(last_used, created_at) DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [ChatRecord(*row) for row in rows]


async def get_chat(chat_id: int) -> Optional[ChatRecord]:
    """Получить чат по ID."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            "SELECT id, user_id, name, provider, api_key, api_url, model, created_at, last_used "
            "FROM chats WHERE id = ?",
            (chat_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return ChatRecord(*row) if row else None


async def delete_chat(chat_id: int) -> None:
    """Удалить чат и все его данные."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        await db.commit()


async def touch_chat(chat_id: int) -> None:
    """Обновить last_used при входе в чат."""
    now = int(time.time())
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute("UPDATE chats SET last_used = ? WHERE id = ?", (now, chat_id))
        await db.commit()


async def update_chat_model(chat_id: int, model: Optional[str]) -> None:
    """Изменить модель чата."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute("UPDATE chats SET model = ? WHERE id = ?", (model, chat_id))
        await db.commit()


# ════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════

PROVIDER_LABELS = {
    "openrouter":  "OpenRouter",
    "favoriteapi": "FavoriteAPI",
    "bai":         "b.ai",
}

PROVIDER_EMOJIS = {
    "openrouter":  "🔀",
    "favoriteapi": "⭐",
    "bai":         "💡",
}


def fmt_ts(ts: Optional[int]) -> str:
    """Форматировать Unix timestamp в читаемую дату."""
    if not ts:
        return "никогда"
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    now = datetime.datetime.now()
    diff = now - dt
    if diff.days == 0:
        return "сегодня"
    if diff.days == 1:
        return "вчера"
    if diff.days < 7:
        return f"{diff.days} д. назад"
    return dt.strftime("%d.%m.%Y")
