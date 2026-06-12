"""providers — LLM provider implementations (OpenRouter, FavoriteAPI, b.ai)."""

from providers.base import BaseProvider, Message, ProviderResponse, ModelInfo, ToolCall
from providers.openrouter import OpenRouterProvider
from providers.favoriteapi import FavoriteAPIProvider
from providers.bai import BaiProvider


def build_provider(settings) -> BaseProvider:
    """
    Factory: build provider from global settings (legacy — used only for health-check).
    For chat-based provider, use build_provider_from_chat().
    """
    provider_name = settings.bot.active_provider
    model         = settings.bot.active_model

    if provider_name == "favoriteapi":
        if not settings.env.favoriteapi_key or not settings.env.favoriteapi_url:
            raise ValueError("FavoriteAPI требует FAVORITEAPI_KEY и FAVORITEAPI_URL")
        return FavoriteAPIProvider(
            api_key       = settings.env.favoriteapi_key,
            base_url      = settings.env.favoriteapi_url,
            default_model = model,
        )

    if provider_name == "bai":
        if not settings.env.bai_api_key:
            raise ValueError("b.ai требует BAI_API_KEY")
        return BaiProvider(
            api_key       = settings.env.bai_api_key,
            default_model = model,
        )

    if not settings.env.openrouter_api_key:
        raise ValueError("OpenRouter требует OPENROUTER_API_KEY")
    return OpenRouterProvider(
        api_key       = settings.env.openrouter_api_key,
        default_model = model,
    )


def build_provider_from_chat(chat) -> BaseProvider:
    """
    Factory: build provider from per-chat config (ChatRecord).
    Используется для всех диалоговых сессий — каждый чат несёт свой api_key.
    """
    if not chat.api_key:
        raise ValueError("В чате не настроен API ключ")

    if chat.provider == "favoriteapi":
        if not chat.api_url:
            raise ValueError("FavoriteAPI требует базовый URL (api_url)")
        return FavoriteAPIProvider(
            api_key       = chat.api_key,
            base_url      = chat.api_url,
            default_model = chat.model,
        )

    if chat.provider == "bai":
        return BaiProvider(
            api_key       = chat.api_key,
            default_model = chat.model,
        )

    # Default: openrouter
    return OpenRouterProvider(
        api_key       = chat.api_key,
        default_model = chat.model,
    )


__all__ = [
    "BaseProvider", "Message", "ProviderResponse", "ModelInfo", "ToolCall",
    "OpenRouterProvider", "FavoriteAPIProvider", "BaiProvider",
    "build_provider", "build_provider_from_chat",
]
