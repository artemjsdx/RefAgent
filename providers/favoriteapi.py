"""
favoriteapi.py — FavoriteAPI LLM provider (self-hosted Gemini bridge).

Key constraints:
- Only ONE request at a time per API key (KEY_BUSY_301 = key is busy)
- Context limit 180KB — tracked via context_kb in every response
- Memory tags in responses are stripped by backend (not visible to user)
- Bootstrap: call /api/v1/me on session start to get current context_kb
"""

import asyncio
import aiohttp
from typing import Optional

from providers.base import BaseProvider, Message, ProviderResponse, ModelInfo, ToolCall
from config.constants import (
    FAVORITEAPI_CHAT_PATH, FAVORITEAPI_ME_PATH,
    FAVORITEAPI_RESET_PATH, FAVORITEAPI_MODELS_PATH,
    FAVORITEAPI_CTX_WARN_KB, FAVORITEAPI_CTX_LIMIT_KB,
)


# ════════════════════════════════════════════════════
# PROVIDER
# ════════════════════════════════════════════════════

class FavoriteAPIProvider(BaseProvider):
    """
    FavoriteAPI — Gemini bridge via Telegram bot.
    Self-hosted, accessed via ngrok/Cloudflare tunnel.
    Single-request-at-a-time per key.
    """

    def __init__(self, api_key: str, base_url: str, default_model: Optional[str] = None):
        self._api_key      = api_key
        self._base_url     = base_url.rstrip("/")
        self._default_model= default_model or "gemini-3.0-flash-thinking"
        self._context_kb   = 0.0
        self._lock         = asyncio.Lock()   # enforce single-request-at-a-time

    @property
    def name(self) -> str:
        return "FavoriteAPI"

    @property
    def context_kb(self) -> float:
        return self._context_kb

    # ════════ BOOTSTRAP ════════

    async def bootstrap(self) -> dict:
        """
        Call /api/v1/me to get current context size and key info.
        Call this once when starting a session.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self._base_url + FAVORITEAPI_ME_PATH,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()

        key_info = data.get("key", {})
        self._context_kb = float(key_info.get("context_kb", 0))
        return data

    # ════════ CHAT ════════

    async def chat(
        self,
        messages:  list[Message],
        tools:     Optional[list[dict]] = None,
        model:     Optional[str]        = None,
    ) -> ProviderResponse:
        """Send chat request. Enforces single-request-at-a-time with asyncio.Lock."""
        async with self._lock:
            return await self._do_chat(messages, tools, model)

    async def _do_chat(
        self,
        messages:  list[Message],
        tools:     Optional[list[dict]],
        model:     Optional[str],
    ) -> ProviderResponse:
        payload: dict = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if model:
            payload["model"] = model
        elif self._default_model:
            payload["model"] = self._default_model

        # FavoriteAPI does not support tool calling natively —
        # tools are injected into system prompt by agent/system_prompt.py

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._base_url + FAVORITEAPI_CHAT_PATH,
                headers=self._headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()

        return self._parse_response(data)

    # ════════ RESET ════════

    async def reset_context(self) -> dict:
        """Reset conversation context for this key. Call when CTX_LIMIT_180 hit."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._base_url + FAVORITEAPI_RESET_PATH,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
        self._context_kb = 0.0
        return data

    # ════════ MODELS ════════

    async def get_models(self) -> list[ModelInfo]:
        """Return hardcoded available models (FavoriteAPI has fixed model list)."""
        return [
            ModelInfo(id="gemini-3.0-flash-thinking",    name="Gemini 3.0 Flash Thinking",    context_length=200_000, is_free=False),
            ModelInfo(id="gemini-3.0-flash",             name="Gemini 3.0 Flash",             context_length=200_000, is_free=False),
            ModelInfo(id="gemini-2.5-flash-thinking",    name="Gemini 2.5 Flash Thinking",    context_length=200_000, is_free=False),
            ModelInfo(id="gemini-2.5-flash",             name="Gemini 2.5 Flash",             context_length=200_000, is_free=False),
            ModelInfo(id="gemini-2.5-mini-thinking",     name="Gemini 2.5 Mini Thinking",     context_length=200_000, is_free=False),
            ModelInfo(id="gemini-2.5-mini",              name="Gemini 2.5 Mini",              context_length=200_000, is_free=False),
            ModelInfo(id="gemini-3.0-flash-thinking-64k",name="Gemini 3.0 Flash Thinking 64k",context_length=64_000,  is_free=False),
            ModelInfo(id="gemini-3.0-flash-64k",         name="Gemini 3.0 Flash 64k",         context_length=64_000,  is_free=False),
        ]

    # ════════ HEALTH ════════

    async def health_check(self) -> bool:
        try:
            data = await self.bootstrap()
            return "key" in data
        except Exception:
            return False

    # ════════ INTERNAL ════════

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }

    def _parse_response(self, data: dict) -> ProviderResponse:
        log_code = data.get("log_code", "")

        # Update tracked context size
        if "context_kb" in data:
            self._context_kb = float(data["context_kb"])

        # Error codes
        if log_code == "KEY_BUSY_301":
            return ProviderResponse(text="[FavoriteAPI: key busy, retry later]", raw=data)
        if log_code == "CTX_LIMIT_180":
            return ProviderResponse(text="[FavoriteAPI: context limit reached, reset required]", raw=data)

        choices = data.get("choices", [])
        if not choices:
            return ProviderResponse(text=f"[FavoriteAPI: empty response, code={log_code}]", raw=data)

        text = choices[0].get("message", {}).get("content", "")
        return ProviderResponse(text=text, context_kb=self._context_kb, raw=data)

    @property
    def needs_compression(self) -> bool:
        return self._context_kb >= FAVORITEAPI_CTX_WARN_KB

    @property
    def at_limit(self) -> bool:
        return self._context_kb >= FAVORITEAPI_CTX_LIMIT_KB
