"""
openrouter.py — OpenRouter LLM provider implementation.
Supports 300+ models via OpenAI-compatible API.
Auto-fallback to next free model on 429 rate-limit.
"""

import time
import json
import logging
import aiohttp
from typing import Optional

from providers.base import BaseProvider, Message, ProviderResponse, ModelInfo, ToolCall
from config.constants import (
    OPENROUTER_BASE_URL, OPENROUTER_CHAT_PATH,
    OPENROUTER_MODELS_PATH, OPENROUTER_MODELS_CACHE_TTL
)

log = logging.getLogger(__name__)

# Free models tried in order when primary is 429 rate-limited
OPENROUTER_FREE_FALLBACKS = [
    "openai/gpt-oss-20b:free",
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.1-8b-instruct",   # cheap paid fallback ~$0.00002/1K
]


# ════════════════════════════════════════════════════
# PROVIDER
# ════════════════════════════════════════════════════

class OpenRouterProvider(BaseProvider):
    """
    OpenRouter provider — OpenAI-compatible API with 300+ models.
    Automatically retries with fallback models on 429 rate-limit.
    Set OPENROUTER_API_KEY in environment to use.
    """

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        self._api_key       = api_key
        self._default_model = default_model or "openai/gpt-oss-20b:free"
        self._models_cache: list[ModelInfo] = []
        self._cache_ts: float = 0.0

    @property
    def name(self) -> str:
        return "OpenRouter"

    # ════════ CHAT ════════

    async def chat(
        self,
        messages:  list[Message],
        tools:     Optional[list[dict]] = None,
        model:     Optional[str]        = None,
    ) -> ProviderResponse:
        payload: dict = {
            "model":    model or self._default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://github.com/artemjsdx/RefAgent",
            "X-Title":       "RefAgent",
        }

        # Build fallback chain: requested model first, then free fallbacks
        primary = payload["model"]
        fallback_chain = [primary] + [m for m in OPENROUTER_FREE_FALLBACKS if m != primary]

        data = {}
        for attempt_model in fallback_chain:
            payload["model"] = attempt_model
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OPENROUTER_BASE_URL + OPENROUTER_CHAT_PATH,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    data = await resp.json()

            err = data.get("error", {}) or {}
            is_rate_limited = (
                resp.status == 429
                or err.get("code") == 429
                or "rate" in str(err.get("message", "")).lower()
            )
            if is_rate_limited:
                log.warning(f"[OpenRouter] {attempt_model} rate-limited → trying next fallback")
                continue

            break   # got a usable response

        return self._parse_response(data)

    # ════════ MODELS ════════

    async def get_models(self) -> list[ModelInfo]:
        """Fetch model list, use cache if fresh (< 1 hour old)."""
        now = time.monotonic()
        if self._models_cache and (now - self._cache_ts) < OPENROUTER_MODELS_CACHE_TTL:
            return self._models_cache

        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                OPENROUTER_BASE_URL + OPENROUTER_MODELS_PATH,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()

        models = []
        for m in data.get("data", []):
            pricing  = m.get("pricing", {})
            prompt_p = _safe_float(pricing.get("prompt", "0"))
            compl_p  = _safe_float(pricing.get("completion", "0"))
            models.append(ModelInfo(
                id               = m.get("id", ""),
                name             = m.get("name", m.get("id", "")),
                context_length   = m.get("context_length", 0),
                is_free          = (prompt_p == 0.0 and compl_p == 0.0),
                price_prompt     = prompt_p,
                price_completion = compl_p,
            ))

        self._models_cache = sorted(models, key=lambda x: (not x.is_free, x.id))
        self._cache_ts     = now
        return self._models_cache

    # ════════ HEALTH ════════

    async def health_check(self) -> bool:
        try:
            models = await self.get_models()
            return len(models) > 0
        except Exception:
            return False

    # ════════ INTERNAL ════════

    @staticmethod
    def _parse_response(data: dict) -> ProviderResponse:
        choices = data.get("choices", [])
        if not choices:
            return ProviderResponse(text="[OpenRouter: empty response]", raw=data)

        message    = choices[0].get("message", {})
        text       = message.get("content")
        tool_calls = []

        for tc in message.get("tool_calls", []):
            fn   = tc.get("function", {})
            args = fn.get("arguments", "{}")
            try:
                args_dict = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                args_dict = {"raw": args}
            tool_calls.append(ToolCall(
                id        = tc.get("id", ""),
                name      = fn.get("name", ""),
                arguments = args_dict,
            ))

        return ProviderResponse(text=text, tool_calls=tool_calls, raw=data)


# ════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════

def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
