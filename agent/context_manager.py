"""
context_manager.py — Управление контекстом FavoriteAPI.

Отслеживает размер контекста (context_kb) после каждого запроса.
При приближении к лимиту — запрашивает сжатие (write:ctx тег).
При достижении лимита — выполняет reset.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from config.constants import FAVORITEAPI_CTX_WARN_KB, FAVORITEAPI_CTX_LIMIT_KB

if TYPE_CHECKING:
    from providers.favoriteapi import FavoriteAPIProvider

log = logging.getLogger(__name__)


class ContextManager:
    """
    Отслеживает размер контекста FavoriteAPI и управляет сжатием/сбросом.

    Состояния:
        NORMAL       — контекст < CTX_WARN_KB (150 KB)
        WARN         — контекст >= CTX_WARN_KB, нужно сжатие
        LIMIT        — контекст >= CTX_LIMIT_KB (180 KB), нужен reset
    """

    def __init__(self) -> None:
        self._context_kb:  float = 0.0
        self._compressed:  bool  = False   # уже запрашивали сжатие в этой сессии
        self._reset_count: int   = 0

    # ════════════════════════════════════════════════
    # STATE
    # ════════════════════════════════════════════════

    @property
    def context_kb(self) -> float:
        return self._context_kb

    @property
    def needs_compression(self) -> bool:
        return self._context_kb >= FAVORITEAPI_CTX_WARN_KB and not self._compressed

    @property
    def at_limit(self) -> bool:
        return self._context_kb >= FAVORITEAPI_CTX_LIMIT_KB

    @property
    def reset_count(self) -> int:
        return self._reset_count

    def update(self, context_kb: Optional[float]) -> None:
        """Обновить отслеживаемый размер контекста из ответа провайдера."""
        if context_kb is not None:
            self._context_kb = context_kb
            if context_kb < FAVORITEAPI_CTX_WARN_KB:
                self._compressed = False   # после reset можно снова сжимать

    def mark_compressed(self) -> None:
        """Отметить что сжатие уже было выполнено."""
        self._compressed = True

    # ════════════════════════════════════════════════
    # ACTIONS
    # ════════════════════════════════════════════════

    async def maybe_compress(
        self,
        provider: "FavoriteAPIProvider",
        messages: list,
    ) -> tuple[bool, list]:
        """
        Если контекст близок к лимиту — добавить запрос на сжатие в messages.
        Возвращает (compressed: bool, updated_messages: list).
        """
        if not self.needs_compression:
            return False, messages

        from agent.system_prompt import build_favoriteapi_compression_prompt
        log.info(f"[ContextManager] Сжатие контекста при {self._context_kb:.1f}KB")

        compress_msg = {"role": "user", "content": build_favoriteapi_compression_prompt()}
        self.mark_compressed()
        return True, messages + [compress_msg]

    async def maybe_reset(self, provider: "FavoriteAPIProvider") -> bool:
        """
        Если достигнут лимит — выполнить reset контекста.
        Возвращает True если reset был выполнен.
        """
        if not self.at_limit:
            return False

        log.warning(f"[ContextManager] Контекст лимит ({self._context_kb:.1f}KB) — reset")
        try:
            await provider.reset_context()
            self._context_kb = 0.0
            self._compressed = False
            self._reset_count += 1
            log.info(f"[ContextManager] Reset #{self._reset_count} выполнен")
            return True
        except Exception as e:
            log.error(f"[ContextManager] Ошибка reset: {e}")
            return False

    def status_text(self) -> str:
        """Статус контекста для отображения пользователю."""
        bar_len  = 10
        filled   = int((self._context_kb / FAVORITEAPI_CTX_LIMIT_KB) * bar_len)
        bar      = "█" * filled + "░" * (bar_len - filled)
        status   = "⚠️" if self.needs_compression else ("🔴" if self.at_limit else "🟢")
        return f"{status} CTX: [{bar}] {self._context_kb:.1f}/{FAVORITEAPI_CTX_LIMIT_KB}KB"


# ── Singleton ──
context_manager = ContextManager()
