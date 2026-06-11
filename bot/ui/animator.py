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

    async def start(self, chat_id: int, action: str = "working") -> int:
        """
        Send an animated status message and return its message_id.
        action: key from FRAMES dict (e.g. "working", "thinking", "reading")
        """
        frames = FRAMES.get(action.lower(), DEFAULT_FRAMES)
        msg    = await self._bot.send_message(chat_id, frames[0])
        task   = asyncio.create_task(
            self._animate(chat_id, msg.message_id, frames)
        )
        self._tasks[msg.message_id] = task
        return msg.message_id

    async def finalize(self, chat_id: int, msg_id: int, log_text: str) -> None:
        """
        Stop animation, delete status message, send permanent log message.
        log_text: the permanent message to show after the action completes.
        """
        await self._stop(msg_id)
        try:
            await self._bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest:
            pass   # message already deleted or too old
        await self._bot.send_message(chat_id, log_text, parse_mode="HTML")

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
        for frame in cycle(frames):
            await asyncio.sleep(ANIMATOR_FRAME_DELAY)
            try:
                await self._bot.edit_message_text(
                    text       = frame,
                    chat_id    = chat_id,
                    message_id = msg_id,
                )
            except TelegramBadRequest:
                break   # message deleted externally — stop silently
            except asyncio.CancelledError:
                raise
