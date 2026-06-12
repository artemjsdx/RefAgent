"""
base.py — Abstract base class for all LLM providers.
Each provider (OpenRouter, FavoriteAPI) must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any


# ════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════

@dataclass
class Message:
    """A single chat message."""
    role:         str            # "system" | "user" | "assistant" | "tool"
    content:      str
    tool_calls:   Optional[list] = None   # assistant → list of tool call dicts (OpenAI format)
    tool_call_id: Optional[str]  = None   # tool role → which call this result belongs to


@dataclass
class ToolCall:
    """A tool invocation requested by the LLM."""
    id:        str
    name:      str
    arguments: dict


@dataclass
class ProviderResponse:
    """Unified response from any LLM provider."""
    text:        Optional[str]       = None       # assistant text (if no tool calls)
    tool_calls:  list[ToolCall]      = field(default_factory=list)
    context_kb:  Optional[float]     = None       # FavoriteAPI: current context size
    raw:         Optional[Any]       = None       # original API response for debugging

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class ModelInfo:
    """Info about a single available model."""
    id:           str
    name:         str
    context_length: int             = 0
    is_free:      bool              = False
    price_prompt: Optional[float]   = None   # USD per 1M input tokens
    price_completion: Optional[float] = None


# ════════════════════════════════════════════════════
# ABSTRACT PROVIDER
# ════════════════════════════════════════════════════

class BaseProvider(ABC):
    """
    Every LLM provider must implement chat(), get_models(), and health_check().
    Providers are stateless — they don't store conversation history.
    History management belongs to agent/react_loop.py.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools:    Optional[list[dict]] = None,
        model:    Optional[str]        = None,
    ) -> ProviderResponse:
        """
        Send messages to the LLM and return a response.
        tools: list of OpenAI-format tool definitions (optional).
        model: override the default model for this call.
        """
        ...

    @abstractmethod
    async def get_models(self) -> list[ModelInfo]:
        """Return available models. May be cached."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable and key is valid."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...
