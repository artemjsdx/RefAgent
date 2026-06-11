"""
state.py — Global agent execution state for RefAgent.

This module tracks whether the ReAct agent is currently running.
Settings handlers check this flag before allowing provider/model changes.

Usage:
    from agent.state import agent_state
    agent_state.is_active   # True if agent is running
    agent_state.set_active(True)
    agent_state.set_active(False)
"""


class AgentState:
    """Simple in-memory agent status tracker. One instance shared globally."""

    def __init__(self) -> None:
        self._active: bool = False
        self.current_chat_id: int | None = None

    @property
    def is_active(self) -> bool:
        return self._active

    def set_active(self, value: bool, chat_id: int | None = None) -> None:
        self._active = value
        self.current_chat_id = chat_id if value else None

    def __repr__(self) -> str:
        return f"AgentState(active={self._active}, chat_id={self.current_chat_id})"


# ── Singleton ──
agent_state = AgentState()
