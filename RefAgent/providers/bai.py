"""
bai.py — b.ai LLM provider (OpenAI-compatible gateway).

b.ai: бесплатный провайдер с 500K токенов на старте.
Бесплатные модели: kimi-k2.5, glm-5, glm-5.1, minimax-m2.5
API: https://api.b.ai/v1 (OpenAI-совместимый)
Docs: https://docs.b.ai/llmservice/api/

Поддерживает нативный tool calling (как OpenAI).
"""

import json
import time
import aiohttp
from typing import Optional

from providers.base import BaseProvider, Message, ProviderResponse, ModelInfo, ToolCall


BAI_BASE_URL     = "https://api.b.ai/v1"
BAI_CHAT_PATH    = "/chat/completions"
BAI_MODELS_PATH  = "/models"

BAI_FREE_MODELS = {
    "kimi-k2.5",
    "glm-5",
    "glm-5.1",
    "minimax-m2.5",
}

BAI_MODELS_CACHE_TTL = 3600   # 1 час


class BaiProvider(BaseProvider):
    """
    b.ai — бесплатный OpenAI-совместимый LLM-шлюз.
    Поддерживает нативный tool calling через /v1/chat/completions.
    """

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        self._api_key       = api_key
        self._default_model = default_model or "kimi-k2.5"
        self._models_cache: list[ModelInfo] = []
        self._cache_ts: float = 0.0

    @property
    def name(self) -> str:
        return "b.ai"

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

        async with aiohttp.ClientSession() as session:
            async with session.post(
                BAI_BASE_URL + BAI_CHAT_PATH,
                headers = self._headers(),
                json    = payload,
                timeout = aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()

        return self._parse_response(data)

    # ════════ MODELS ════════

    async def get_models(self) -> list[ModelInfo]:
        """Получить список доступных моделей. Кешируется на 1 час."""
        now = time.monotonic()
        if self._models_cache and (now - self._cache_ts) < BAI_MODELS_CACHE_TTL:
            return self._models_cache

        async with aiohttp.ClientSession() as session:
            async with session.get(
                BAI_BASE_URL + BAI_MODELS_PATH,
                headers = self._headers(),
                timeout = aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()

        models = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            models.append(ModelInfo(
                id              = mid,
                name            = mid,
                context_length  = 200_000,
                is_free         = mid in BAI_FREE_MODELS,
            ))

        # Сначала бесплатные, потом платные
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

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }

    @staticmethod
    def _parse_response(data: dict) -> ProviderResponse:
        choices = data.get("choices", [])
        if not choices:
            return ProviderResponse(
                text = f"[b.ai: пустой ответ] {data.get('error', {}).get('message', '')}",
                raw  = data,
            )

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
