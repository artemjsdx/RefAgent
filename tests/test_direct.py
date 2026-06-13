#!/usr/bin/env python3
"""
test_direct.py — Прямой запуск агента без Telegram UI.

Загружает 24 сессии из data/sessions/ и запускает ReAct-цикл с задачей.
Весь вывод идёт в stdout + data/test_run.log.
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# Работаем из корня RefAgent
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

LOG_FILE = ROOT / "data" / "test_run.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger("test_direct")

# ── Конфиг теста ──────────────────────────────────────────────────────────────
CHAT_ID   = 4
PROVIDER  = "bai"
API_KEY   = "sk-15k64k8qm997wqb62744u7i9vi836dqh"
MODEL     = "kimi-k2.5"

TASK = (
    "рефка: http://t.me/StarsovComBot?start=0o6gxsKB7\n\n"
    "Нужно зайти в этого бота и выполнить 3 задания чтобы реф засчитался. "
    "Аккаунтов 24 штуки, прогони всех по очереди."
)


# ── Загрузка сессий ───────────────────────────────────────────────────────────

async def load_sessions() -> int:
    from tools.db import init_db, get_accounts_for_chat
    from tools.session_tools import load_session_file
    from config.constants import SESSIONS_DIR

    await init_db()

    # Проверяем уже загруженные
    existing = await get_accounts_for_chat(CHAT_ID)
    if existing:
        log.info(f"Аккаунты уже в базе: {len(existing)} шт. — пропускаем загрузку.")
        return len(existing)

    session_files = sorted(SESSIONS_DIR.glob("*.session"))
    log.info(f"Найдено .session файлов: {len(session_files)}")

    ok_count = 0
    for sf in session_files:
        res = await load_session_file(sf, chat_id=CHAT_ID)
        if res.ok and "skipped" not in (res.error or ""):
            ok_count += 1
            log.info(f"  ✅ {res.phone} (id={res.account_id})")
        elif res.ok:
            log.info(f"  ⏭  {res.phone} — {res.error}")
        else:
            log.warning(f"  ❌ {res.phone} — {res.error}")

    log.info(f"Загружено: {ok_count} / {len(session_files)}")
    return ok_count


# ── Запуск агента ─────────────────────────────────────────────────────────────

async def run_agent():
    from providers.bai import BaiProvider
    from agent.react_loop import ReactLoop
    from agent.status_event import StatusEvent
    from config.constants import SESSIONS_DIR

    provider = BaiProvider(api_key=API_KEY, default_model=MODEL)

    status_lines: list[str] = []

    ICONS = {
        "thinking":   "🧠",
        "thought":    "💭",
        "status":     "💬",
        "tool_call":  "🔧",
        "tool_result":"📋",
        "warn":       "⚠️",
        "error":      "❌",
        "done":       "✅",
        "step":       "📌",
        "wait":       "⏳",
        "retry":      "🔄",
    }

    async def log_cb(event: StatusEvent):
        k = event.kind
        d = event.data
        icon = ICONS.get(k, "·")

        if k == "tool_call":
            line = f"{icon} [{d.get('tool')}] {d.get('args_preview','')[:80]}"
        elif k in ("thought", "status"):
            line = f"{icon} {d.get('text','')[:120]}"
        elif k == "tool_result":
            line = f"{icon} {d.get('tool')} → {d.get('result_preview','')[:80]}"
        elif k == "step":
            line = f"{icon} Шаг {d.get('n')}/{d.get('total')}: {d.get('desc','')}"
        elif k in ("warn", "error"):
            line = f"{icon} {d.get('text','')}"
        elif k == "done":
            line = f"{icon} DONE: {d.get('text','')[:80]}"
        else:
            line = f"[{k}] {d}"

        status_lines.append(line)
        print(f"\033[36m{line}\033[0m", flush=True)

    react = ReactLoop(provider=provider, log_cb=log_cb)

    log.info("=" * 60)
    log.info("ЗАДАЧА:")
    log.info(TASK)
    log.info("=" * 60)

    result = await react.run(
        chat_id          = CHAT_ID,
        user_message     = TASK,
        initial_messages = [],
        session_dir      = str(SESSIONS_DIR),
    )

    # Сохраняем полный отчёт
    report_path = ROOT / "data" / "test_result.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("ЗАДАЧА:\n" + TASK + "\n\n")
        f.write("ЛОГ СОБЫТИЙ:\n")
        for line in status_lines:
            f.write(line + "\n")
        f.write("\n\nИТОГ АГЕНТА:\n" + result)

    log.info("=" * 60)
    log.info("ИТОГ:")
    print(result)
    log.info(f"Отчёт сохранён → {report_path}")
    return result


# ── Точка входа ───────────────────────────────────────────────────────────────

async def main():
    log.info("=== RefAgent Direct Test ===")

    n = await load_sessions()
    if n == 0:
        log.error("Нет загруженных аккаунтов — выход.")
        sys.exit(1)

    await run_agent()


if __name__ == "__main__":
    asyncio.run(main())
