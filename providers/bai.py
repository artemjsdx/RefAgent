"""
  bai.py — b.ai LLM provider (OpenAI-compatible gateway).

  b.ai: бесплатный провайдер с 500K токенов на старте.
  ВАЖНО: kimi-k2.5 не поддерживает нативный tool_calling через b.ai API.
  Реагирует ошибкой "Field required" если передать tools.
  Поэтому b.ai использует TEXT-based tool calling (как FavoriteAPI).
  """

  import json
  import time
  import aiohttp
  from typing import Optional

  from providers.base import BaseProvider, Message, ProviderResponse, ModelInfo, ToolCall


  BAI_BASE_URL    = "https://api.b.ai/v1"
  BAI_CHAT_PATH   = "/chat/completions"
  BAI_MODELS_PATH = "/models"

  BAI_FREE_MODELS = {"kimi-k2.5", "glm-5", "glm-5.1", "minimax-m2.5"}
  BAI_MODELS_CACHE_TTL = 3600

  # b.ai использует text-based tool calling (флаг читает react_loop)
  USE_TEXT_TOOLS = True


  class BaiProvider(BaseProvider):
      """
      b.ai — бесплатный OpenAI-совместимый LLM-шлюз.
      Использует TEXT-based tool calling: инструменты описываются в системном промпте,
      модель отвечает тегами <tool_call>...</tool_call> как FavoriteAPI.
      """

      # Флаг для react_loop — не передавать tools в API payload
      uses_text_tools: bool = True

      def __init__(self, api_key: str, default_model: Optional[str] = None):
          self._api_key       = api_key
          self._default_model = default_model or "kimi-k2.5"
          self._models_cache: list[ModelInfo] = []
          self._cache_ts: float = 0.0

      @property
      def name(self) -> str:
          return "b.ai"

      async def chat(
          self,
          messages: list[Message],
          tools:    Optional[list[dict]] = None,
          model:    Optional[str]        = None,
      ) -> ProviderResponse:
          # b.ai/kimi-k2.5 не поддерживает native tool calling — tools игнорируем.
          # Инструменты уже в системном промпте (react_loop добавляет при uses_text_tools=True).
          payload: dict = {
              "model":    model or self._default_model,
              "messages": [self._serialize_message(m) for m in messages],
          }

          async with aiohttp.ClientSession() as session:
              async with session.post(
                  BAI_BASE_URL + BAI_CHAT_PATH,
                  headers = self._headers(),
                  json    = payload,
                  timeout = aiohttp.ClientTimeout(total=120),
              ) as resp:
                  if resp.content_type == "application/json":
                      data = await resp.json()
                  else:
                      txt = await resp.text()
                      return ProviderResponse(
                          text=f"[b.ai: неожиданный content-type] {txt[:200]}",
                      )

          return self._parse_response(data)

      async def get_models(self) -> list[ModelInfo]:
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
                  id=mid, name=mid, context_length=200_000,
                  is_free=mid in BAI_FREE_MODELS,
              ))
          self._models_cache = sorted(models, key=lambda x: (not x.is_free, x.id))
          self._cache_ts = now
          return self._models_cache

      async def health_check(self) -> bool:
          try:
              return len(await self.get_models()) > 0
          except Exception:
              return False

      def _headers(self) -> dict:
          return {
              "Authorization": f"Bearer {self._api_key}",
              "Content-Type":  "application/json",
          }

      @staticmethod
      def _serialize_message(m: Message) -> dict:
          """Сериализовать Message → dict для b.ai API."""
          if m.role == "tool":
              # b.ai не знает role=tool, конвертируем в user
              return {"role": "user", "content": f"[Tool Result] {m.content or ''}"}
          if m.role == "assistant" and m.tool_calls:
              # Убрать tool_calls из assistant message (b.ai не поддерживает)
              return {"role": "assistant", "content": m.content or ""}
          return {"role": m.role, "content": m.content or ""}

      @staticmethod
      def _parse_response(data: dict) -> ProviderResponse:
          choices = data.get("choices", [])
          if not choices:
              err = data.get("error", {})
              msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
              return ProviderResponse(
                  text=f"[b.ai ошибка] {msg}" if msg else "[b.ai: пустой ответ]",
                  raw=data,
              )
          text = choices[0].get("message", {}).get("content") or ""
          return ProviderResponse(text=text, tool_calls=[], raw=data)
  