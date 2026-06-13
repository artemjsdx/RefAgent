"""
animator.py — Animated status blocks for RefAgent bot UI.

Usage pattern:
    anim = Animator(bot)
    msg_id = await anim.start(chat_id, "Working")
    # ... do work ...
    await anim.finalize(chat_id, msg_id, "Connected to account +7921*****")

The status message cycles through frames (Working → Working. → Working.. → Working...)
via edit_message in a background asyncio task. When finalize() is called, the status
message is deleted and a permanent log message is sent instead.
"""

import asyncio
import json
from itertools import cycle
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from config.constants import ANIMATOR_FRAME_DELAY


# ════════════════════════════════════════════════════
# FRAME SETS — pick by action type
# ════════════════════════════════════════════════════

FRAMES = {
    "working":    ["Working",    "Working.",    "Working..",    "Working..."],
    "thinking":   ["Thinking",   "Thinking.",   "Thinking..",   "Thinking..."],
    "reading":    ["Read",       "Read.",       "Read..",       "Read..."],
    "sending":    ["Sending",    "Sending.",    "Sending..",    "Sending..."],
    "connecting": ["Connecting", "Connecting.", "Connecting..", "Connecting..."],
    "joining":    ["Joining",    "Joining.",    "Joining..",    "Joining..."],
    "scanning":   ["Scanning",   "Scanning.",   "Scanning..",   "Scanning..."],
    "planning":   ["Planning",   "Planning.",   "Planning..",   "Planning..."],
    "searching":  ["Searching",  "Searching.",  "Searching..",  "Searching..."],
    "saving":     ["Saving",     "Saving.",     "Saving..",     "Saving..."],
}

DEFAULT_FRAMES = FRAMES["working"]


# ════════════════════════════════════════════════════
# ANIMATOR
# ════════════════════════════════════════════════════

class Animator:
    """
    Manages animated status messages for a single bot instance.
    One Animator instance is shared across the entire application.
    """

    def __init__(self, bot: Bot):
        self._bot   = bot
        self._tasks: dict[int, asyncio.Task] = {}   # message_id -> animation task

    async def start(self, chat_id: int, action: str = "working", reply_markup=None) -> int:
        """
        Send an animated status message and return its message_id.
        action: key from FRAMES dict (e.g. "working", "thinking", "reading")
        reply_markup: optional ReplyKeyboardMarkup to attach (e.g. running_keyboard())
        """
        frames = FRAMES.get(action.lower(), DEFAULT_FRAMES)
        msg    = await self._bot.send_message(chat_id, frames[0], reply_markup=reply_markup)
        task   = asyncio.create_task(
            self._animate(chat_id, msg.message_id, frames)
        )
        self._tasks[msg.message_id] = task
        return msg.message_id

    async def finalize(self, chat_id: int, msg_id: int, log_text: str, reply_markup=None) -> None:
        """
        Stop animation, delete status message, send permanent log message.
        log_text: the permanent message to show after the action completes.
        reply_markup: optional ReplyKeyboardMarkup to attach (e.g. idle_keyboard())
        """
        await self._stop(msg_id)
        try:
            await self._bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest:
            pass   # message already deleted or too old
        await self._bot.send_message(chat_id, log_text, parse_mode="HTML", reply_markup=reply_markup)

    async def stop_only(self, msg_id: int) -> None:
        """Stop animation without deleting or sending log (for error cases)."""
        await self._stop(msg_id)

    # ════════ INTERNAL ════════

    async def _stop(self, msg_id: int) -> None:
        task = self._tasks.pop(msg_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _animate(self, chat_id: int, msg_id: int, frames: list[str]) -> None:
        """Background task: cycles through frames, editing the message."""
        frames_iter = cycle(frames)
        next(frames_iter)   # SKIP first frame — already sent via send_message, editing to
                            # same text raises TelegramBadRequest "message is not modified"
        for frame in frames_iter:
            await asyncio.sleep(ANIMATOR_FRAME_DELAY)
            try:
                await self._bot.edit_message_text(
                    text       = frame,
                    chat_id    = chat_id,
                    message_id = msg_id,
                )
            except TelegramBadRequest:
                break   # message deleted or not modified — stop silently
            except asyncio.CancelledError:
                raise
            except Exception:
                break   # any other Telegram error — stop silently


# ════════════════════════════════════════════════════
# COMPOUND BLOCK — accumulating log + animated status
# ════════════════════════════════════════════════════

# Maps tool name → animation status type (None = keep current / no change)
TOOL_STATUS: dict[str, Optional[str]] = {
    "connect_account":        "connecting",
    "disconnect_account":     "working",
    "join_channel":           "joining",
    "conductor_join_group":   "joining",
    "start_bot":              "working",
    "send_message":           "sending",
    "get_messages":           "reading",
    "wait_bot_response":      "reading",
    "get_inline_button_urls": "reading",
    "click_button":           "working",
    "search_library":         "searching",
    "search_skills":          "searching",
    "use_skill":              "searching",
    "write_library":          "saving",
    "load_sessions":          "scanning",
    "list_accounts":          "scanning",
    "conductor_setup":        "connecting",
    "conductor_cleanup":      "working",
    "execute_command":        "working",
    "run_temp_script":        "working",
    "propose_plan":           "planning",
    "sleep_seconds":          None,
}


def _short_url(url: str) -> str:
    """Extract @handle from t.me URL or truncate."""
    if not url:
        return "?"
    if "t.me/" in url:
        part = url.split("t.me/")[-1].split("?")[0].strip("/")
        return f"@{part[:20]}"
    return url[-20:]


def make_action_line(tool: str, args_preview: str = "") -> Optional[str]:
    """
    Generate a human-readable log line for a tool call.
    Returns None for silent tools (e.g. sleep_seconds) — no log line shown.
    """
    try:
        args: dict = json.loads(args_preview) if args_preview else {}
    except Exception:
        args = {}

    table: dict = {
        "list_accounts":          "🔍 Checking accounts",
        "load_sessions":          "📁 Loading sessions",
        "connect_account":        lambda a: f"🔌 {a.get('phone', '?')}",
        "disconnect_account":     lambda a: f"⏏️  {a.get('phone', '?')}",
        "join_channel":           lambda a: f"📢 {_short_url(a.get('url', '?'))}",
        "conductor_join_group":   "👥 Joining group",
        "start_bot":              lambda a: f"🤖 @{a.get('username', '?')}",
        "send_message":           "✉️ Sending message",
        "get_messages":           "📖 Reading messages",
        "wait_bot_response":      "⏳ Waiting response",
        "get_inline_button_urls": "🔍 Reading buttons",
        "click_button":           lambda a: f"🖱 {a.get('text', '?')[:25]}",
        "search_library":         lambda a: f"📚 {a.get('query', '?')[:30]}",
        "search_skills":          lambda a: f"📚 Skills: {a.get('query', '?')[:25]}",
        "use_skill":              lambda a: f"📚 {a.get('name', '?')}",
        "write_library":          "📚 Saving",
        "execute_command":        lambda a: f">_ {a.get('command', '?')[:40]}",
        "run_temp_script":        "🐍 Script",
        "propose_plan":           "📋 Plan",
        "sleep_seconds":          None,   # silent — no log line
        "conductor_setup":        "🎭 Conductor setup",
        "conductor_cleanup":      "🎭 Cleanup",
    }

    entry = table.get(tool, f"⚙️ {tool}")
    if entry is None:
        return None
    if callable(entry):
        line = entry(args)
        return line if line else f"⚙️ {tool}"
    return entry


class CompoundBlock:
    """
    A single Telegram message that shows accumulating tool-action log lines
    with an animated status line at the bottom.

    Visual (updates in-place via edit):
        📁 Loading sessions
        🔌 +79001234567
        Scanning..

    Lifecycle:
        block = CompoundBlock(bot)
        await block.start(chat_id, "thinking", reply_markup=running_keyboard())

        # on each tool call:
        await block.add_log("📁 Loading sessions", new_status="scanning")

        # on thought:
        await block.finalize_log()         # removes status, log stays as permanent msg
        await bot.send_message(...)        # send the thought
        await block.start(chat_id, ...)   # fresh block for next round

        # on final result:
        await block.finalize(result_html, reply_markup=idle_keyboard())

        # on cancel:
        await block.stop_only()
    """

    MAX_LOG = 8   # oldest lines are trimmed when exceeded

    def __init__(self, bot: Bot) -> None:
        self._bot    = bot
        self.chat_id: Optional[int]       = None
        self.msg_id:  Optional[int]       = None
        self._log:    list[str]           = []
        self._frames: list[str]           = FRAMES["thinking"]
        self._task:   Optional[asyncio.Task] = None

    # ── Public API ────────────────────────────────────────────────────────

    async def start(
        self,
        chat_id:     int,
        status:      str = "thinking",
        reply_markup = None,
    ) -> int:
        """Send a new block message and start animation. Returns msg_id."""
        self.chat_id = chat_id
        self._log    = []
        self._frames = FRAMES.get(status.lower(), DEFAULT_FRAMES)
        msg = await self._bot.send_message(
            chat_id,
            self._frames[0],
            reply_markup=reply_markup,
        )
        self.msg_id = msg.message_id
        self._task  = asyncio.create_task(self._animate())
        return msg.message_id

    async def add_log(self, line: str, new_status: Optional[str] = None) -> None:
        """
        Append an action log line and optionally switch status frames.
        Stops current animation, edits message in-place, restarts animation.
        """
        await self._stop_task()
        self._log.append(line)
        if len(self._log) > self.MAX_LOG:
            self._log = self._log[-self.MAX_LOG:]
        if new_status:
            self._frames = FRAMES.get(new_status.lower(), DEFAULT_FRAMES)
        if self.msg_id:
            try:
                await self._bot.edit_message_text(
                    self._render(self._frames[0]),
                    chat_id    = self.chat_id,
                    message_id = self.msg_id,
                )
            except Exception:
                pass
        self._task = asyncio.create_task(self._animate())

    async def switch_status(self, new_status: str) -> None:
        """Switch status animation frames without adding a log line."""
        await self._stop_task()
        self._frames = FRAMES.get(new_status.lower(), DEFAULT_FRAMES)
        if self.msg_id:
            try:
                await self._bot.edit_message_text(
                    self._render(self._frames[0]),
                    chat_id    = self.chat_id,
                    message_id = self.msg_id,
                )
            except Exception:
                pass
        self._task = asyncio.create_task(self._animate())

    async def finalize_log(self) -> None:
        """
        Stop animation, edit message to show only log lines (remove animated status).
        The message stays as a permanent log entry.
        Sets msg_id = None so the next start() creates a fresh message.
        If log is empty, deletes the message entirely.
        """
        await self._stop_task()
        if self.msg_id:
            if self._log:
                try:
                    await self._bot.edit_message_text(
                        "\n".join(self._log),
                        chat_id    = self.chat_id,
                        message_id = self.msg_id,
                    )
                except Exception:
                    pass
            else:
                try:
                    await self._bot.delete_message(self.chat_id, self.msg_id)
                except Exception:
                    pass
        self.msg_id = None

    async def finalize(
        self,
        result_text:  Optional[str] = None,
        reply_markup  = None,
    ) -> None:
        """Stop animation, delete current block message, optionally send result."""
        await self._stop_task()
        if self.msg_id:
            try:
                await self._bot.delete_message(self.chat_id, self.msg_id)
            except Exception:
                pass
            self.msg_id = None
        if result_text:
            await self._bot.send_message(
                self.chat_id,
                result_text,
                parse_mode   = "HTML",
                reply_markup = reply_markup,
            )

    async def stop_only(self) -> None:
        """Cancel animation and delete current block message."""
        await self._stop_task()
        if self.msg_id:
            try:
                await self._bot.delete_message(self.chat_id, self.msg_id)
            except Exception:
                pass
            self.msg_id = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _render(self, status_frame: str) -> str:
        return "\n".join(list(self._log) + [status_frame])

    async def _stop_task(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _animate(self) -> None:
        """Cycle through status frames, editing the last line of the block message."""
        frame_iter = cycle(self._frames)
        next(frame_iter)   # skip first — already shown via send_message / edit_message_text
        try:
            for frame in frame_iter:
                await asyncio.sleep(ANIMATOR_FRAME_DELAY)
                if not self.msg_id:
                    break
                try:
                    await self._bot.edit_message_text(
                        self._render(frame),
                        chat_id    = self.chat_id,
                        message_id = self.msg_id,
                    )
                except TelegramBadRequest:
                    break
                except Exception:
                    break
        except asyncio.CancelledError:
            raise
