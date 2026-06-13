"""
history_db.py — Персистентная история сообщений чата.

Хранит диалог (user/assistant) на диске — история сохраняется между перезапусками бота.
Ключ: chat_record_id — ID записи в таблице chats (не Telegram chat_id).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import aiosqlite

from config.constants import SESSIONS_DB


# ════════════════════════════════════════════════════
# SCHEMA
# ════════════════════════════════════════════════════

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_record_id INTEGER NOT NULL,
    role           TEXT    NOT NULL,   -- user | assistant | system
    content        TEXT    NOT NULL,
    ts             INTEGER NOT NULL    -- unix timestamp
);
CREATE INDEX IF NOT EXISTS idx_history_chat ON chat_history (chat_record_id, ts);
"""


@dataclass
class HistoryMessage:
    role:    str
    content: str
    ts:      int = 0


# ════════════════════════════════════════════════════
# INIT
# ════════════════════════════════════════════════════

async def ensure_history_table() -> None:
    """Создать таблицу если не существует. Вызывать при старте."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.executescript(HISTORY_SCHEMA)
        await db.commit()


# ════════════════════════════════════════════════════
# ЗАПИСЬ
# ════════════════════════════════════════════════════

async def save_message(chat_record_id: int, role: str, content: str) -> None:
    """Сохранить одно сообщение в историю."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute(
            "INSERT INTO chat_history (chat_record_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (chat_record_id, role, content, int(time.time())),
        )
        await db.commit()


async def save_pair(chat_record_id: int, user_text: str, assistant_text: str) -> None:
    """Сохранить пару user+assistant за одну транзакцию."""
    now = int(time.time())
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute(
            "INSERT INTO chat_history (chat_record_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (chat_record_id, "user", user_text, now),
        )
        await db.execute(
            "INSERT INTO chat_history (chat_record_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (chat_record_id, "assistant", assistant_text, now + 1),
        )
        await db.commit()


# ════════════════════════════════════════════════════
# ЧТЕНИЕ
# ════════════════════════════════════════════════════

async def load_history(
    chat_record_id: int,
    limit:          int = 20,
) -> list[HistoryMessage]:
    """
    Вернуть последние `limit` сообщений (user+assistant), отсортированных по времени.
    Системные сообщения не возвращаются — они генерируются свежими каждый раз.
    """
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            """
            SELECT role, content, ts FROM (
                SELECT role, content, ts
                FROM chat_history
                WHERE chat_record_id = ? AND role != 'system'
                ORDER BY ts DESC
                LIMIT ?
            ) ORDER BY ts ASC
            """,
            (chat_record_id, limit),
        ) as cur:
            rows = await cur.fetchall()

    return [HistoryMessage(role=r[0], content=r[1], ts=r[2]) for r in rows]


async def get_message_count(chat_record_id: int) -> int:
    """Количество сообщений в истории чата."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM chat_history WHERE chat_record_id = ?",
            (chat_record_id,),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


# ════════════════════════════════════════════════════
# ОЧИСТКА
# ════════════════════════════════════════════════════

async def clear_history(chat_record_id: int) -> int:
    """Очистить историю чата. Возвращает число удалённых записей."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        cur = await db.execute(
            "DELETE FROM chat_history WHERE chat_record_id = ?",
            (chat_record_id,),
        )
        await db.commit()
        return cur.rowcount
