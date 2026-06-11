"""
plan_manager.py — Управление планом задачи агента.

Хранит план в data/plan.txt (одна строка = один шаг).
Предоставляет CRUD для шагов и статус выполнения.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from config.constants import DATA_DIR


PLAN_FILE = DATA_DIR / "plan.txt"


# ════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════

class StepStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    FAILED   = "failed"
    SKIPPED  = "skipped"


@dataclass
class PlanStep:
    index:       int
    description: str
    status:      StepStatus = StepStatus.PENDING
    result:      Optional[str] = None


@dataclass
class Plan:
    description: str
    ref_url:     str
    steps:       list[PlanStep] = field(default_factory=list)
    current_idx: int = 0

    @property
    def is_done(self) -> bool:
        return all(s.status in (StepStatus.DONE, StepStatus.SKIPPED) for s in self.steps)

    @property
    def current_step(self) -> Optional[PlanStep]:
        if 0 <= self.current_idx < len(self.steps):
            return self.steps[self.current_idx]
        return None

    @property
    def progress(self) -> tuple[int, int]:
        done = sum(1 for s in self.steps if s.status in (StepStatus.DONE, StepStatus.SKIPPED))
        return done, len(self.steps)

    def format_text(self) -> str:
        """Отформатировать план для отображения пользователю."""
        lines = [
            "<b>📋 ПЛАН ЗАДАЧИ</b>",
            "",
            f"<i>{self.description}</i>",
        ]
        if self.ref_url:
            lines.append(f"<b>Реф:</b> <code>{self.ref_url}</code>")
        lines.append("")
        for step in self.steps:
            icon = {
                StepStatus.PENDING: "⬜",
                StepStatus.RUNNING: "🔄",
                StepStatus.DONE:    "✅",
                StepStatus.FAILED:  "❌",
                StepStatus.SKIPPED: "⏭",
            }.get(step.status, "⬜")
            lines.append(f"{icon} {step.index + 1}. {step.description}")
            if step.result:
                lines.append(f"    <i>{step.result}</i>")
        return "\n".join(lines)


# ════════════════════════════════════════════════════
# MANAGER
# ════════════════════════════════════════════════════

class PlanManager:
    """Singleton-менеджер текущего плана."""

    def __init__(self) -> None:
        self._plan:  Optional[Plan] = None
        self._lock:  asyncio.Lock   = asyncio.Lock()

    @property
    def has_plan(self) -> bool:
        return self._plan is not None

    @property
    def plan(self) -> Optional[Plan]:
        return self._plan

    async def create(
        self,
        steps:       list[str],
        description: str = "",
        ref_url:     str = "",
    ) -> Plan:
        async with self._lock:
            plan_steps = [PlanStep(index=i, description=s) for i, s in enumerate(steps)]
            self._plan = Plan(
                description = description,
                ref_url     = ref_url,
                steps       = plan_steps,
            )
            await self._save()
            return self._plan

    async def update_step(
        self,
        index:  int,
        status: StepStatus,
        result: Optional[str] = None,
    ) -> None:
        async with self._lock:
            if self._plan and 0 <= index < len(self._plan.steps):
                self._plan.steps[index].status = status
                if result:
                    self._plan.steps[index].result = result
                if status == StepStatus.DONE:
                    # Продвинуть current_idx к следующему pending шагу
                    for i, s in enumerate(self._plan.steps):
                        if s.status == StepStatus.PENDING:
                            self._plan.current_idx = i
                            break
                await self._save()

    async def advance(self) -> Optional[PlanStep]:
        """Перейти к следующему незавершённому шагу."""
        async with self._lock:
            if not self._plan:
                return None
            for i, step in enumerate(self._plan.steps):
                if step.status == StepStatus.PENDING:
                    self._plan.current_idx = i
                    return step
            return None

    async def cancel(self) -> None:
        async with self._lock:
            self._plan = None
            if PLAN_FILE.exists():
                PLAN_FILE.unlink()

    async def load_from_disk(self) -> Optional[Plan]:
        """Восстановить план из plan.txt при перезапуске."""
        if not PLAN_FILE.exists():
            return None
        try:
            lines = PLAN_FILE.read_text(encoding="utf-8").splitlines()
            if not lines:
                return None
            description = lines[0] if lines else ""
            ref_url     = lines[1] if len(lines) > 1 else ""
            steps       = [PlanStep(index=i, description=s) for i, s in enumerate(lines[2:])]
            self._plan  = Plan(description=description, ref_url=ref_url, steps=steps)
            return self._plan
        except Exception:
            return None

    async def _save(self) -> None:
        if not self._plan:
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        lines = [
            self._plan.description,
            self._plan.ref_url,
            *[s.description for s in self._plan.steps],
        ]
        PLAN_FILE.write_text("\n".join(lines), encoding="utf-8")


# ── Singleton ──
plan_manager = PlanManager()
