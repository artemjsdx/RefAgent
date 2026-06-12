"""
file_buffer.py — Буфер прикреплённых файлов для чата с агентом.

Ключ буфера — sandbox_id (active_chat_id из ChatRecord), а НЕ Telegram chat_id.
Это обеспечивает изоляцию файлов между разными именованными чатами:
файлы, прикреплённые в «Чат1», не попадут в «Чат2».

Использование:
  push_file(sandbox_id, attachment)   — добавить вложение в буфер
  pop_files(sandbox_id)               — забрать все вложения и очистить буфер
  has_files(sandbox_id)               — проверить, есть ли ожидающие вложения
  clear_files(sandbox_id)             — очистить буфер без возврата

FileAttachment.context_line()        — строка для вставки в контекст агента
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ════════════════════════════════════════════════════
# DATA CLASS
# ════════════════════════════════════════════════════

@dataclass
class FileAttachment:
    """Одно вложение из Telegram-чата."""

    file_id:   str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_path: Optional[str] = None   # локальный путь после скачивания (если скачано)
    caption:   Optional[str] = None
    size:      int = 0                # размер в байтах (0 если неизвестен)

    def context_line(self) -> str:
        """
        Строка для вставки в пользовательское сообщение агенту.
        Например: '[Файл: data.json | MIME: application/json | 4 КБ]'
        """
        name = self.file_name or self.file_id
        parts = [f"[Файл: {name}"]
        if self.mime_type:
            parts.append(f"MIME: {self.mime_type}")
        if self.size:
            parts.append(f"{self.size // 1024} КБ")
        if self.file_path:
            parts.append(f"путь: {self.file_path}")
        if self.caption:
            parts.append(f"подпись: {self.caption}")
        return " | ".join(parts) + "]"


# ════════════════════════════════════════════════════
# IN-MEMORY БУФЕР
# ════════════════════════════════════════════════════

# sandbox_id (active_chat_id) → список FileAttachment
_buffer: dict[Optional[int], list[FileAttachment]] = {}


def push_file(sandbox_id: Optional[int], attachment: FileAttachment) -> None:
    """Добавить вложение в буфер для данного чата (sandbox_id = active_chat_id)."""
    if sandbox_id not in _buffer:
        _buffer[sandbox_id] = []
    _buffer[sandbox_id].append(attachment)


def pop_files(sandbox_id: Optional[int]) -> list[FileAttachment]:
    """
    Забрать все вложения из буфера и очистить его.
    Возвращает пустой список если вложений нет.
    """
    return _buffer.pop(sandbox_id, [])


def has_files(sandbox_id: Optional[int]) -> bool:
    """Проверить есть ли ожидающие вложения для данного чата."""
    return bool(_buffer.get(sandbox_id))


def clear_files(sandbox_id: Optional[int]) -> None:
    """Явно очистить буфер без возврата (например при отмене задачи)."""
    _buffer.pop(sandbox_id, None)
