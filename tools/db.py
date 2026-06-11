"""
db.py — Асинхронная работа с SQLite базой данных RefAgent.

Схема:
  accounts — все загруженные Telegram-аккаунты с их параметрами
  
КРИТИЧНО: UNIQUE index на api_id — жёсткий запрет одного api_id на несколько аккаунтов.
Нарушение = массовая заморозка аккаунтов.
"""

import aiosqlite
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from config.constants import SESSIONS_DB


# ════════════════════════════════════════════════════
# DATA CLASS
# ════════════════════════════════════════════════════

@dataclass
class AccountRecord:
    phone:        str
    uid:          Optional[int]
    api_id:       int
    api_hash:     str
    format:       str            # TELETHON | TDESKTOP | UNKNOWN
    status:       str            # ACTIVE | FROZEN | BANNED | UNKNOWN
    uid_category: str            # OLD | NORMAL | FRESH | UNKNOWN
    is_conductor: bool
    session_path: str
    id:           Optional[int] = None
    added_at:     Optional[str] = None
    last_used:    Optional[str] = None


# ════════════════════════════════════════════════════
# SCHEMA
# ════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    phone        TEXT    NOT NULL,
    uid          INTEGER,
    api_id       INTEGER NOT NULL,
    api_hash     TEXT    NOT NULL,
    format       TEXT    NOT NULL DEFAULT 'UNKNOWN',
    status       TEXT    NOT NULL DEFAULT 'ACTIVE',
    uid_category TEXT    NOT NULL DEFAULT 'UNKNOWN',
    is_conductor INTEGER NOT NULL DEFAULT 0,
    session_path TEXT    NOT NULL,
    added_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    last_used    TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_id
    ON accounts(api_id);
"""


# ════════════════════════════════════════════════════
# INIT
# ════════════════════════════════════════════════════

async def init_db() -> None:
    """Создать таблицы при первом запуске. Безопасно вызывать повторно."""
    SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ════════════════════════════════════════════════════
# ЗАПИСЬ
# ════════════════════════════════════════════════════

class DuplicateApiIdError(Exception):
    """api_id уже используется другим аккаунтом — жёсткий запрет."""
    pass


async def add_account(rec: AccountRecord) -> int:
    """
    Добавить аккаунт в БД. Возвращает id новой записи.
    Бросает DuplicateApiIdError если api_id уже занят.
    """
    async with aiosqlite.connect(SESSIONS_DB) as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO accounts
                    (phone, uid, api_id, api_hash, format, status, uid_category,
                     is_conductor, session_path, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.phone,
                    rec.uid,
                    rec.api_id,
                    rec.api_hash,
                    rec.format,
                    rec.status,
                    rec.uid_category,
                    int(rec.is_conductor),
                    rec.session_path,
                    datetime.now().isoformat(sep=" ", timespec="seconds"),
                ),
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError as e:
            if "idx_api_id" in str(e) or "UNIQUE" in str(e):
                raise DuplicateApiIdError(
                    f"api_id {rec.api_id} уже используется другим аккаунтом. "
                    f"Использование одного api_id для нескольких аккаунтов ведёт к массовой заморозке!"
                ) from e
            raise


# ════════════════════════════════════════════════════
# ЧТЕНИЕ
# ════════════════════════════════════════════════════

async def get_all_accounts() -> list[AccountRecord]:
    """Вернуть все аккаунты, новые первыми."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts ORDER BY added_at DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_record(r) for r in rows]


async def get_account(account_id: int) -> Optional[AccountRecord]:
    """Вернуть один аккаунт по id или None."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ) as cur:
            row = await cur.fetchone()
    return _row_to_record(row) if row else None


async def get_conductor() -> Optional[AccountRecord]:
    """Вернуть текущего проводника или None."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE is_conductor = 1 LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    return _row_to_record(row) if row else None


async def api_id_exists(api_id: int) -> bool:
    """Проверить, занят ли api_id."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            "SELECT 1 FROM accounts WHERE api_id = ?", (api_id,)
        ) as cur:
            return await cur.fetchone() is not None


# ════════════════════════════════════════════════════
# ОБНОВЛЕНИЕ
# ════════════════════════════════════════════════════

async def set_conductor(account_id: int, value: bool) -> None:
    """Назначить или снять статус проводника. Только один проводник единовременно."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        if value:
            await db.execute("UPDATE accounts SET is_conductor = 0")
        await db.execute(
            "UPDATE accounts SET is_conductor = ? WHERE id = ?",
            (int(value), account_id),
        )
        await db.commit()


async def update_status(account_id: int, status: str) -> None:
    """Обновить статус аккаунта (ACTIVE / FROZEN / BANNED)."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute(
            "UPDATE accounts SET status = ? WHERE id = ?",
            (status, account_id),
        )
        await db.commit()


async def update_last_used(account_id: int) -> None:
    """Зафиксировать время последнего использования."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute(
            "UPDATE accounts SET last_used = ? WHERE id = ?",
            (datetime.now().isoformat(sep=" ", timespec="seconds"), account_id),
        )
        await db.commit()


async def delete_account(account_id: int) -> None:
    """Удалить аккаунт из БД (файл сессии остаётся на диске)."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()


# ════════════════════════════════════════════════════
# ВНУТРЕННИЕ ХЕЛПЕРЫ
# ════════════════════════════════════════════════════

def _row_to_record(row) -> AccountRecord:
    return AccountRecord(
        id           = row["id"],
        phone        = row["phone"],
        uid          = row["uid"],
        api_id       = row["api_id"],
        api_hash     = row["api_hash"],
        format       = row["format"],
        status       = row["status"],
        uid_category = row["uid_category"],
        is_conductor = bool(row["is_conductor"]),
        session_path = row["session_path"],
        added_at     = row["added_at"],
        last_used    = row["last_used"],
    )
