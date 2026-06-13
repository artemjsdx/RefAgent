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
    chat_id:      Optional[int] = None   # к какому чату относится аккаунт


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
    last_used    TEXT,
    chat_id      INTEGER
);
"""


# ════════════════════════════════════════════════════
# INIT
# ════════════════════════════════════════════════════

async def init_db() -> None:
    """Создать таблицы при первом запуске. Безопасно вызывать повторно."""
    from tools.chat_db import CHATS_SCHEMA
    from tools.history_db import HISTORY_SCHEMA
    SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(SESSIONS_DB) as db:
        # WAL режим: параллельные читатели не блокируют писателя
        await db.execute("PRAGMA journal_mode=WAL;")
        # Ждать до 5с вместо немедленного SQLITE_BUSY
        await db.execute("PRAGMA busy_timeout=5000;")
        await db.executescript(SCHEMA)
        await db.executescript(CHATS_SCHEMA)
        await db.executescript(HISTORY_SCHEMA)
        # Миграция: добавить chat_id если ещё нет (для существующих БД)
        try:
            await db.execute("ALTER TABLE accounts ADD COLUMN chat_id INTEGER")
        except Exception:
            pass  # колонка уже есть
        # ── Skills stats ──────────────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS skill_stats (
                name       TEXT PRIMARY KEY,
                used_count INTEGER NOT NULL DEFAULT 0,
                last_used  TEXT
            )
        """)
        await db.commit()


async def session_path_exists(session_path: str) -> bool:
    """Проверить, загружена ли уже сессия с таким путём."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            "SELECT 1 FROM accounts WHERE session_path = ?", (session_path,)
        ) as cur:
            return await cur.fetchone() is not None


async def phone_exists(phone: str) -> bool:
    """Проверить, есть ли уже аккаунт с таким телефоном."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        async with db.execute(
            "SELECT 1 FROM accounts WHERE phone = ?", (phone,)
        ) as cur:
            return await cur.fetchone() is not None


# ════════════════════════════════════════════════════
# ЗАПИСЬ
# ════════════════════════════════════════════════════

class DuplicateApiIdError(Exception):
    """api_id уже используется другим аккаунтом — жёсткий запрет."""
    pass


async def add_account(rec: AccountRecord) -> int:
    """Добавить аккаунт в БД. Возвращает id новой записи."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        cursor = await db.execute(
            """
            INSERT INTO accounts
                (phone, uid, api_id, api_hash, format, status, uid_category,
                 is_conductor, session_path, added_at, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                rec.chat_id,
            ),
        )
        await db.commit()
        return cursor.lastrowid


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


async def get_accounts_for_chat(chat_id: int) -> list[AccountRecord]:
    """Вернуть аккаунты конкретного чата (песочница по chat_id)."""
    async with aiosqlite.connect(SESSIONS_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE chat_id = ? ORDER BY added_at DESC",
            (chat_id,),
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
# СТАТИСТИКА ЗАДАЧ
# ════════════════════════════════════════════════════

async def get_task_stats() -> dict:
    """
    Вернуть агрегированную статистику по задачам из results.db.
    Безопасно если таблица ещё не создана — возвращает нули.
    """
    from config.constants import RESULTS_DB
    if not RESULTS_DB.exists():
        return {"tasks_done": 0, "refs_total": 0}
    try:
        async with aiosqlite.connect(RESULTS_DB) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM task_results"
            ) as cur:
                tasks_done = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT COALESCE(SUM(refs_credited), 0) FROM task_results"
            ) as cur:
                refs_total = (await cur.fetchone())[0]
        return {"tasks_done": tasks_done, "refs_total": refs_total}
    except Exception:
        return {"tasks_done": 0, "refs_total": 0}


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
        chat_id      = row["chat_id"] if "chat_id" in row.keys() else None,
    )
