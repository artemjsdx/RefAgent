"""
status_blocks.py — Helpers for sending permanent log messages and reports.

These are the non-animated, persistent messages between agent actions.
They form the "IDE activity log" visible in the chat during agent execution.
"""

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup


# ════════════════════════════════════════════════════
# LOG HELPERS
# ════════════════════════════════════════════════════

async def send_log(bot: Bot, chat_id: int, text: str) -> int:
    """Send a permanent log line. Returns message_id."""
    msg = await bot.send_message(chat_id, text, parse_mode="HTML")
    return msg.message_id


async def send_section(bot: Bot, chat_id: int, title: str) -> int:
    """Send a section divider (bold title line between action groups)."""
    text = f"<b>{title}</b>"
    msg  = await bot.send_message(chat_id, text, parse_mode="HTML")
    return msg.message_id


async def send_error(bot: Bot, chat_id: int, text: str) -> int:
    """Send an error log line."""
    msg = await bot.send_message(chat_id, f"<b>Error:</b> {text}", parse_mode="HTML")
    return msg.message_id


async def send_report(bot: Bot, chat_id: int, report: str,
                      keyboard: InlineKeyboardMarkup | None = None) -> int:
    """Send a final task report (monospace table format)."""
    msg = await bot.send_message(
        chat_id      = chat_id,
        text         = report,
        parse_mode   = "HTML",
        reply_markup = keyboard,
    )
    return msg.message_id


# ════════════════════════════════════════════════════
# REPORT BUILDER
# ════════════════════════════════════════════════════

def build_task_report(
    total:    int,
    success:  int,
    failed:   int,
    skipped:  int,
    details:  list[tuple[str, str]],   # [(phone_masked, status_text), ...]
    ref_url:  str = "",
) -> str:
    """
    Build a formatted HTML task completion report.
    Uses <pre> for table-like alignment since native tables aren't in Bot API yet.
    """
    lines = [
        "<b>ОТЧЁТ ЗАДАЧИ</b>",
        "",
        "<pre>",
        f"{'Обработано':<14} {total}",
        f"{'Засчитано':<14} {success}",
        f"{'Пропущено':<14} {skipped}",
        f"{'Ошибок':<14} {failed}",
        "</pre>",
    ]

    if ref_url:
        lines += ["", f"<b>Реф:</b> {ref_url}"]

    if details:
        lines += ["", "<b>Детали:</b>", "<pre>"]
        for phone, status in details:
            lines.append(f"{phone:<18} {status}")
        lines.append("</pre>")

    return "\n".join(lines)
