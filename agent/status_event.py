"""
status_event.py — Типизированные события статуса для ReAct-агента.

StatusEvent передаётся в log_cb callback на каждом шаге агента.
UI-слой (chat.py) выбирает нужный status_block в зависимости от kind.

Виды событий (KIND_*):
  KIND_THINKING     — агент думает (LLM call in progress)
  KIND_THOUGHT      — агент выдал текст-мысль (промежуточный)
  KIND_TOOL_CALL    — вызов инструмента начат
  KIND_TOOL_RESULT  — результат инструмента получен
  KIND_STEP         — шаг плана (n из total)
  KIND_WAIT         — агент ждёт (sleep между рефералами)
  KIND_RETRY        — retry после ошибки
  KIND_WARN         — предупреждение (не фатальное)
  KIND_ERROR        — ошибка
  KIND_STOP         — остановка по команде пользователя
  KIND_DONE         — агент завершил работу
  KIND_SEPARATOR    — разделитель между аккаунтами/этапами
  KIND_CONTEXT_RESET — контекст FavoriteAPI был сброшен
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


# ════════════════════════════════════════════════════
# КОНСТАНТЫ ВИДОВ СОБЫТИЙ
# ════════════════════════════════════════════════════

KIND_THINKING      = "thinking"
KIND_THOUGHT       = "thought"
KIND_TOOL_CALL     = "tool_call"
KIND_TOOL_RESULT   = "tool_result"
KIND_STEP          = "step"
KIND_WAIT          = "wait"
KIND_RETRY         = "retry"
KIND_WARN          = "warn"
KIND_ERROR         = "error"
KIND_STOP          = "stop"
KIND_DONE          = "done"
KIND_SEPARATOR     = "separator"
KIND_CONTEXT_RESET = "context_reset"


# ════════════════════════════════════════════════════
# DATA CLASS
# ════════════════════════════════════════════════════

@dataclass
class StatusEvent:
    """
    Одно событие статуса от ReAct-агента.

    kind: строка из KIND_* констант
    data: словарь с деталями события (зависит от kind)

    Типичные поля data по kind:
      thinking:      {iteration: int}
      thought:       {text: str}
      tool_call:     {tool: str, args_preview: str}
      tool_result:   {tool: str, result_preview: str}
      step:          {n: int, total: int, desc: str}
      wait:          {seconds: int, reason: str}
      retry:         {attempt: int, reason: str}
      warn:          {text: str}
      error:         {text: str}
      stop:          {}
      done:          {text: str}
      separator:     {}
      context_reset: {text: str}
    """

    kind: str
    data: dict[str, Any] = field(default_factory=dict)


# ════════════════════════════════════════════════════
# CALLBACK TYPE
# ════════════════════════════════════════════════════

# Async callback принимает StatusEvent и ничего не возвращает
StatusCallback = Callable[[StatusEvent], Coroutine[Any, Any, None]]
