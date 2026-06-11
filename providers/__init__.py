"""providers — LLM provider implementations (OpenRouter, FavoriteAPI)."""

from providers.base import BaseProvider, Message, ProviderResponse, ModelInfo, ToolCall
from providers.openrouter import OpenRouterProvider
from providers.favoriteapi import FavoriteAPIProvider


def build_provider(settings) -> BaseProvider:
    """
    Factory: build the active provider from current settings.
    Called on startup and when user switches provider in settings menu.
    """
    provider_name = settings.bot.active_provider
    model         = settings.bot.active_model

    if provider_name == "favoriteapi":
        if not settings.env.favoriteapi_key or not settings.env.favoriteapi_url:
            raise ValueError("FavoriteAPI requires FAVORITEAPI_KEY and FAVORITEAPI_URL env vars")
        return FavoriteAPIProvider(
            api_key      = settings.env.favoriteapi_key,
            base_url     = settings.env.favoriteapi_url,
            default_model= model,
        )

    # Default: openrouter
    if not settings.env.openrouter_api_key:
        raise ValueError("OpenRouter requires OPENROUTER_API_KEY env var")
    return OpenRouterProvider(
        api_key      = settings.env.openrouter_api_key,
        default_model= model,
    )


__all__ = [
    "BaseProvider", "Message", "ProviderResponse", "ModelInfo", "ToolCall",
    "OpenRouterProvider", "FavoriteAPIProvider", "build_provider",
]
