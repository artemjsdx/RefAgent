"""
report.py — Финальный отчёт задачи и хранение истории в results.db.

Функции:
  send_final_report  — отправить красиво оформленный отчёт в чат
  save_task_result   — сохранить результат в data/results.db
  get_task_history   — получить историю задач
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from aiogram import Bot
from bot.keyboards.main_menu import back_to_main_keyboard
from config.constants import RESULTS_DB

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════
# INIT DB
# ════════════════════════════════════════════════════

async def init_results_db() -> None:
    """Создать таблицу task_results если её нет."""
    RESULTS_DB.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(RESULTS_DB)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT    NOT NULL,
                description TEXT,
                ref_url     TEXT,
                steps_json  TEXT,
                result_text TEXT,
                success     INTEGER DEFAULT 0
            )
        """)
        await db.commit()


# ════════════════════════════════════════════════════
# SAVE
# ════════════════════════════════════════════════════

async def save_task_result(plan, result_text: str) -> None:
    """Сохранить результат выполненной задачи в results.db."""
    try:
        await init_results_db()
        steps_json = json.dumps(
            [s.description for s in plan.steps],
            ensure_ascii=False,
        )
        success = 1 if "✅" in result_text or "засчитан" in result_text.lower() else 0
        async with aiosqlite.connect(str(RESULTS_DB)) as db:
            await db.execute("""
                INSERT INTO task_results (created_at, description, ref_url, steps_json, result_text, success)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                plan.description,
                plan.ref_url,
                steps_json,
                result_text[:4000],
                success,
            ))
            await db.commit()
    except Exception as e:
        log.error(f"[Report] Ошибка сохранения: {e}")


# ════════════════════════════════════════════════════
# SEND REPORT
# ════════════════════════════════════════════════════

async def send_final_report(bot: Bot, chat_id: int, result_text: str, plan) -> None:
    """Отправить финальный отчёт в рамке."""
    done, total = plan.progress

    report_lines = [
        "╔══════════════════════════════╗",
        "║      ОТЧЁТ ЗАДАЧИ             ║",
        "╚══════════════════════════════╝",
        "",
    ]

    if plan.description:
        report_lines.append(f"<b>Задача:</b> {plan.description}")
    if plan.ref_url:
        report_lines.append(f"<b>Реф:</b> <code>{plan.ref_url}</code>")

    report_lines += [
        "",
        "<pre>",
        f"{'Шагов выполнено':<20} {done}/{total}",
        "</pre>",
        "",
    ]

    # Статусы шагов
    step_lines = []
    for step in plan.steps:
        icon = {
            "pending": "⬜", "running": "🔄",
            "done": "✅", "failed": "❌", "skipped": "⏭",
        }.get(step.status.value, "⬜")
        line = f"{icon} {step.description}"
        if step.result:
            line += f"\n    <i>{step.result[:80]}</i>"
        step_lines.append(line)

    report_lines += step_lines
    report_lines += ["", "─" * 32, ""]

    # Краткий итог из result_text (первые 500 символов)
    summary = result_text[:500]
    if len(result_text) > 500:
        summary += "…"
    report_lines.append(summary)

    report_text = "\n".join(report_lines)

    try:
        await bot.send_message(
            chat_id      = chat_id,
            text         = report_text,
            parse_mode   = "HTML",
            reply_markup = back_to_main_keyboard(),
        )
    except Exception as e:
        log.error(f"[Report] Ошибка отправки отчёта: {e}")
        # Fallback — короткое сообщение
        await bot.send_message(
            chat_id      = chat_id,
            text         = f"<b>Задача завершена</b>\n\n{result_text[:1000]}",
            parse_mode   = "HTML",
            reply_markup = back_to_main_keyboard(),
        )


# ════════════════════════════════════════════════════
# HISTORY
# ════════════════════════════════════════════════════

async def get_task_history(limit: int = 20) -> list[dict]:
    """Получить историю задач из results.db."""
    try:
        await init_results_db()
        async with aiosqlite.connect(str(RESULTS_DB)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM task_results ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"[Report] Ошибка чтения истории: {e}")
        return []


async def get_stats() -> dict:
    """Статистика задач для главного меню."""
    try:
        await init_results_db()
        async with aiosqlite.connect(str(RESULTS_DB)) as db:
            total   = (await (await db.execute("SELECT COUNT(*) FROM task_results")).fetchone())[0]
            success = (await (await db.execute("SELECT COUNT(*) FROM task_results WHERE success=1")).fetchone())[0]
            return {"total": total, "success": success, "failed": total - success}
    except Exception:
        return {"total": 0, "success": 0, "failed": 0}
