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
    msg = await bot.send_message(chat_id, f"❌ <b>Ошибка:</b> {text}", parse_mode="HTML")
    return msg.message_id


# ════════════════════════════════════════════════════
# AGENT STATUS BLOCKS
# ════════════════════════════════════════════════════

async def send_thought(bot: Bot, chat_id: int, text: str) -> int:
    """Агент выдал промежуточную мысль."""
    safe = text[:500]
    msg  = await bot.send_message(chat_id, f"💭 {safe}", parse_mode="HTML")
    return msg.message_id


async def send_tool_call(bot: Bot, chat_id: int, tool: str, args_preview: str = "") -> int:
    """Агент вызывает инструмент."""
    text = f"🔧 <code>{tool}</code>"
    if args_preview:
        text += f"\n<code>{args_preview[:120]}</code>"
    msg = await bot.send_message(chat_id, text, parse_mode="HTML")
    return msg.message_id


async def send_tool_result(bot: Bot, chat_id: int, tool: str, result_preview: str = "") -> int:
    """Результат вызова инструмента."""
    text = f"✅ <code>{tool}</code>"
    if result_preview:
        text += f": {result_preview[:120]}"
    msg = await bot.send_message(chat_id, text, parse_mode="HTML")
    return msg.message_id


async def send_step(bot: Bot, chat_id: int, n: int, total: int, desc: str = "") -> int:
    """Шаг плана N из total."""
    text = f"<b>Шаг {n}/{total}</b>"
    if desc:
        text += f" — {desc}"
    msg = await bot.send_message(chat_id, text, parse_mode="HTML")
    return msg.message_id


async def send_wait(bot: Bot, chat_id: int, seconds: int, reason: str = "") -> int:
    """Пауза между действиями (rate limiter)."""
    reason_text = f" ({reason})" if reason else ""
    msg = await bot.send_message(
        chat_id,
        f"⏱ <b>Пауза {seconds}с{reason_text}</b>",
        parse_mode="HTML",
    )
    return msg.message_id


async def send_retry(bot: Bot, chat_id: int, attempt: int, reason: str = "") -> int:
    """Повторная попытка после ошибки."""
    text = f"🔄 Повтор #{attempt}"
    if reason:
        text += f": {reason[:80]}"
    msg = await bot.send_message(chat_id, text, parse_mode="HTML")
    return msg.message_id


async def send_warn(bot: Bot, chat_id: int, text: str) -> int:
    """Предупреждение (не фатальное)."""
    msg = await bot.send_message(chat_id, f"⚠️ {text[:300]}", parse_mode="HTML")
    return msg.message_id


async def send_separator(bot: Bot, chat_id: int) -> int:
    """Разделитель между аккаунтами / этапами."""
    msg = await bot.send_message(chat_id, "─" * 20)
    return msg.message_id


async def send_ok(bot: Bot, chat_id: int, text: str) -> int:
    """Успешное действие."""
    msg = await bot.send_message(chat_id, f"✅ {text}", parse_mode="HTML")
    return msg.message_id


async def send_account(bot: Bot, chat_id: int, phone: str, status: str) -> int:
    """Статус обработки конкретного аккаунта."""
    # Маскируем середину номера: +14707526421 → +1470***421
    masked = phone
    if len(phone) > 7:
        masked = phone[:4] + "***" + phone[-3:]
    msg = await bot.send_message(
        chat_id,
        f"👤 <code>{masked}</code> — {status}",
        parse_mode="HTML",
    )
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
