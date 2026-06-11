"""
settings.py — Configuration loader for RefAgent.
Loads API keys from environment variables and bot settings from config.json.
Bot token is stored in config.json only — never in environment.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

from config.constants import CONFIG_FILE, DATA_DIR, SESSIONS_DIR, LIBRARY_DIR, SCRIPTS_DIR


# ════════════════════════════════════════════════════
# DATA CLASSES
# ════════════════════════════════════════════════════

@dataclass
class BotConfig:
    """Settings persisted in config.json (non-sensitive, user preferences)."""
    bot_token:       Optional[str] = None
    active_provider: str           = "openrouter"   # "openrouter" | "favoriteapi"
    active_model:    Optional[str] = None           # model id string, None = provider default


@dataclass
class EnvConfig:
    """Settings loaded from environment variables (sensitive)."""
    openrouter_api_key: Optional[str] = None
    favoriteapi_key:    Optional[str] = None
    favoriteapi_url:    Optional[str] = None
    github_token:       Optional[str] = None


@dataclass
class Settings:
    """Combined settings for the entire application."""
    bot:  BotConfig = field(default_factory=BotConfig)
    env:  EnvConfig = field(default_factory=EnvConfig)


# ════════════════════════════════════════════════════
# LOADER
# ════════════════════════════════════════════════════

def load_settings() -> Settings:
    """Load settings from env vars + config.json. Creates dirs if needed."""
    _ensure_dirs()

    env = EnvConfig(
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY"),
        favoriteapi_key    = os.getenv("FAVORITEAPI_KEY"),
        favoriteapi_url    = os.getenv("FAVORITEAPI_URL"),
        github_token       = os.getenv("GITHUB_TOKEN"),
    )

    bot = _load_bot_config()
    return Settings(bot=bot, env=env)


def save_bot_config(config: BotConfig) -> None:
    """Persist bot config to config.json."""
    CONFIG_FILE.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def _load_bot_config() -> BotConfig:
    """Read config.json, return defaults if missing or malformed."""
    if not CONFIG_FILE.exists():
        return BotConfig()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return BotConfig(
            bot_token       = data.get("bot_token"),
            active_provider = data.get("active_provider", "openrouter"),
            active_model    = data.get("active_model"),
        )
    except (json.JSONDecodeError, KeyError):
        return BotConfig()


def _ensure_dirs() -> None:
    """Create required data directories if they don't exist."""
    for d in [DATA_DIR, SESSIONS_DIR, LIBRARY_DIR, SCRIPTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════
# GLOBAL SINGLETON (set after interactive startup)
# ════════════════════════════════════════════════════

_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def set_settings(s: Settings) -> None:
    global _settings
    _settings = s
