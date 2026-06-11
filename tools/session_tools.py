"""
session_tools.py — Загрузка и разбор Telegram-сессий.

Поддерживает:
  - .session файлы (Telethon SQLite формат)
  - .zip архивы с .session + .json sidecar файлами

КРИТИЧНО: api_id и api_hash ВСЕГДА берутся из sidecar .json файла рядом с .session.
Никогда не использовать глобальные credentials — массовая заморозка аккаунтов.
"""

import re
import json
import sqlite3
import zipfile
import shutil
from pathlib import Path
from typing import Optional

from config.constants import (
    SESSIONS_DIR,
    UID_THRESHOLD_FRESH,
    UID_THRESHOLD_NORMAL,
)
from tools.db import AccountRecord, DuplicateApiIdError, add_account, api_id_exists


# ════════════════════════════════════════════════════
# ФОРМАТЫ И КАТЕГОРИИ
# ════════════════════════════════════════════════════

SQLITE_MAGIC = b"SQLite format 3\x00"

FORMAT_TELETHON = "TELETHON"
FORMAT_TDESKTOP = "TDESKTOP"
FORMAT_UNKNOWN  = "UNKNOWN"

CATEGORY_OLD       = "OLD"
CATEGORY_NORMAL    = "NORMAL"
CATEGORY_FRESH     = "FRESH"
CATEGORY_UNKNOWN   = "UNKNOWN"

STATUS_ACTIVE  = "ACTIVE"
STATUS_FROZEN  = "FROZEN"
STATUS_BANNED  = "BANNED"
STATUS_UNKNOWN = "UNKNOWN"

PHONE_RE = re.compile(r"(\+?\d{10,15})")


# ════════════════════════════════════════════════════
# ДЕТЕКТ ФОРМАТА
# ════════════════════════════════════════════════════

def detect_format(path: Path) -> str:
    """
    Определить формат .session файла.
    Возвращает TELETHON | TDESKTOP | UNKNOWN.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        if not header.startswith(SQLITE_MAGIC):
            return FORMAT_UNKNOWN

        conn   = sqlite3.connect(str(path))
        tables = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        if "sessions" in tables and "entities" in tables:
            return FORMAT_TELETHON
        return FORMAT_TDESKTOP

    except Exception:
        return FORMAT_UNKNOWN


# ════════════════════════════════════════════════════
# SIDECAR JSON
# ════════════════════════════════════════════════════

def read_sidecar_json(session_path: Path) -> dict:
    """
    Прочитать .json файл рядом с .session.
    Ожидаемые ключи: app_id (int), app_hash (str).
    Бросает ValueError если файл не найден или ключи отсутствуют.
    """
    json_path = session_path.with_suffix(".json")
    if not json_path.exists():
        raise ValueError(
            f"Sidecar JSON не найден: {json_path.name}\n"
            f"Каждый .session файл должен иметь рядом .json с app_id и app_hash."
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка разбора {json_path.name}: {e}") from e

    api_id   = data.get("app_id") or data.get("api_id")
    api_hash = data.get("app_hash") or data.get("api_hash")

    if not api_id:
        raise ValueError(f"{json_path.name}: не найден app_id / api_id")
    if not api_hash:
        raise ValueError(f"{json_path.name}: не найден app_hash / api_hash")

    return {"api_id": int(api_id), "api_hash": str(api_hash)}


# ════════════════════════════════════════════════════
# UID
# ════════════════════════════════════════════════════

def extract_uid_from_session(session_path: Path) -> Optional[int]:
    """
    Прочитать user_id из таблицы sessions Telethon-сессии.
    Возвращает None если не удалось.
    """
    try:
        conn = sqlite3.connect(str(session_path))
        row  = conn.execute(
            "SELECT user_id FROM sessions LIMIT 1"
        ).fetchone()
        conn.close()
        return int(row[0]) if row and row[0] else None
    except Exception:
        return None


def extract_phone_from_session(session_path: Path) -> Optional[str]:
    """
    Попытаться вытащить номер телефона из имени файла сессии.
    Telethon обычно называет файлы по номеру телефона: +79001234567.session
    """
    stem = session_path.stem
    m    = PHONE_RE.search(stem)
    return m.group(1) if m else stem   # если не нашли — используем имя файла


def categorize_uid(uid: Optional[int]) -> str:
    """Определить категорию аккаунта по UID."""
    if uid is None:
        return CATEGORY_UNKNOWN
    if uid < UID_THRESHOLD_NORMAL:
        return CATEGORY_OLD
    if uid < UID_THRESHOLD_FRESH:
        return CATEGORY_NORMAL
    return CATEGORY_FRESH


# ════════════════════════════════════════════════════
# ЗАГРУЗКА ОДНОЙ СЕССИИ
# ════════════════════════════════════════════════════

class SessionLoadResult:
    """Результат попытки загрузки одной сессии."""
    def __init__(
        self,
        phone:   str,
        ok:      bool,
        account_id: Optional[int] = None,
        error:   Optional[str]    = None,
    ):
        self.phone      = phone
        self.ok         = ok
        self.account_id = account_id
        self.error      = error

    def __repr__(self) -> str:
        return f"SessionLoadResult(phone={self.phone}, ok={self.ok}, error={self.error})"


async def load_session_file(session_path: Path) -> SessionLoadResult:
    """
    Загрузить одну .session в БД.
    
    Шаги:
      1. detect_format
      2. read_sidecar_json (ОБЯЗАТЕЛЬНО)
      3. extract_uid + categorize
      4. Проверить уникальность api_id
      5. Вставить в accounts
    """
    phone = extract_phone_from_session(session_path)

    try:
        fmt = detect_format(session_path)
        if fmt == FORMAT_UNKNOWN:
            return SessionLoadResult(phone, ok=False,
                error="Неизвестный формат — не SQLite. Поддерживается только Telethon.")

        sidecar  = read_sidecar_json(session_path)
        api_id   = sidecar["api_id"]
        api_hash = sidecar["api_hash"]

        uid      = extract_uid_from_session(session_path) if fmt == FORMAT_TELETHON else None
        category = categorize_uid(uid)

        rec = AccountRecord(
            phone        = phone,
            uid          = uid,
            api_id       = api_id,
            api_hash     = api_hash,
            format       = fmt,
            status       = STATUS_ACTIVE,
            uid_category = category,
            is_conductor = False,
            session_path = str(session_path),
        )

        acc_id = await add_account(rec)
        return SessionLoadResult(phone, ok=True, account_id=acc_id)

    except DuplicateApiIdError as e:
        return SessionLoadResult(phone, ok=False, error=str(e))
    except ValueError as e:
        return SessionLoadResult(phone, ok=False, error=str(e))
    except Exception as e:
        return SessionLoadResult(phone, ok=False, error=f"Неожиданная ошибка: {e}")


# ════════════════════════════════════════════════════
# ЗАГРУЗКА ZIP-АРХИВА
# ════════════════════════════════════════════════════

async def extract_and_load_zip(zip_path: Path) -> list[SessionLoadResult]:
    """
    Распаковать .zip архив и загрузить все найденные .session файлы.
    Ожидает структуру: файлы .session и .json рядом в архиве.
    
    Возвращает список результатов для каждой найденной сессии.
    """
    extract_dir = SESSIONS_DIR / zip_path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        return [SessionLoadResult(zip_path.name, ok=False, error="Файл повреждён или не является ZIP")]

    session_files = list(extract_dir.rglob("*.session"))
    if not session_files:
        return [SessionLoadResult(zip_path.name, ok=False, error="В архиве нет .session файлов")]

    results = []
    for sf in session_files:
        # Копируем sidecar JSON рядом с session если он в подпапке
        json_src = sf.with_suffix(".json")
        if not json_src.exists():
            # Поищем в корне архива
            alt = extract_dir / sf.with_suffix(".json").name
            if alt.exists():
                shutil.copy(alt, json_src)

        result = await load_session_file(sf)
        results.append(result)

    return results


# ════════════════════════════════════════════════════
# ФОРМАТИРОВАНИЕ ОТЧЁТА
# ════════════════════════════════════════════════════

def format_load_report(results: list[SessionLoadResult]) -> str:
    """Сформировать HTML-отчёт о загрузке сессий."""
    ok_list  = [r for r in results if r.ok]
    err_list = [r for r in results if not r.ok]

    lines = [
        "<b>Результат загрузки сессий</b>",
        "",
        f"Загружено: {len(ok_list)} / {len(results)}",
    ]

    if ok_list:
        lines += ["", "<b>Успешно:</b>"]
        for r in ok_list:
            lines.append(f"  {r.phone}")

    if err_list:
        lines += ["", "<b>Ошибки:</b>"]
        for r in err_list:
            lines.append(f"  {r.phone}: {r.error}")

    return "\n".join(lines)
