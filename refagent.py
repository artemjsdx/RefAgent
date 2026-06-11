"""
refagent.py — Точка входа RefAgent.

Запуск: python refagent.py

При старте:
  1. Интерактивный ввод токена бота (Enter = оставить из config.json)
  2. Инициализация БД (data/sessions.db, data/results.db)
  3. Запуск aiogram бота
  4. Работает до Ctrl+C
"""

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import load_settings, save_bot_config, set_settings
from config.constants import BOT_NAME, BOT_VERSION


# ════════════════════════════════════════════════════
# ЛОГИРОВАНИЕ
# ════════════════════════════════════════════════════

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt= "%H:%M:%S",
)
log = logging.getLogger(BOT_NAME)


# ════════════════════════════════════════════════════
# ВВОД ТОКЕНА
# ════════════════════════════════════════════════════

def prompt_token(existing: str | None) -> str:
    import os
    print(f"\n{'=' * 50}")
    print(f"  {BOT_NAME} v{BOT_VERSION}")
    print(f"{'=' * 50}")

    # Env var перекрывает всё (Replit secrets / CI)
    env_token = os.getenv("BOT_TOKEN")
    if env_token:
        masked = env_token[:8] + "..." + env_token[-4:]
        print(f"\n  Токен из env: {masked}")
        return env_token

    # Уже есть токен в config.json — не спрашиваем, запускаем сразу
    if existing:
        masked = existing[:8] + "..." + existing[-4:]
        print(f"\n  Токен из config: {masked}")
        return existing

    # Только если совсем нет токена — спрашиваем интерактивно
    print("\n  Токен бота не настроен.")
    while True:
        answer = input("  Введи токен от @BotFather: ").strip()
        if answer:
            return answer
        print("  Токен не может быть пустым.")


# ════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ ХЕНДЛЕРОВ
# ════════════════════════════════════════════════════

def register_handlers(dp: Dispatcher, bot: Bot) -> None:
    from bot.ui.animator import Animator
    from bot.handlers.start         import router as start_router
    from bot.handlers.settings_menu import router as settings_router
    from bot.handlers.sessions      import router as sessions_router, set_animator as set_sessions_animator
    from bot.handlers.chat          import router as chat_router, set_animator as set_chat_animator

    animator = Animator(bot)
    set_sessions_animator(animator)
    set_chat_animator(animator)

    # Порядок важен: sessions до start (чтобы CB_SESSIONS не перехватил placeholder)
    dp.include_router(sessions_router)
    dp.include_router(chat_router)
    dp.include_router(settings_router)
    dp.include_router(start_router)


# ════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════

async def main() -> None:
    from tools.db import init_db
    from bot.ui.report import init_results_db

    settings = load_settings()
    token    = prompt_token(settings.bot.bot_token)
    settings.bot.bot_token = token
    save_bot_config(settings.bot)
    set_settings(settings)

    print(f"\n  Провайдер: {settings.bot.active_provider}")
    print(f"  Модель:    {settings.bot.active_model or 'по умолчанию'}")

    # Показать статус API ключей
    env = settings.env
    key_status = []
    if env.openrouter_api_key:
        key_status.append("OpenRouter ✓")
    if env.favoriteapi_key:
        key_status.append("FavoriteAPI ✓")
    if env.bai_api_key:
        key_status.append("b.ai ✓")
    if not key_status:
        key_status.append("⚠ API ключи не найдены!")
    print(f"  API ключи: {', '.join(key_status)}")

    print(f"\n  Инициализация базы данных...")
    await init_db()
    await init_results_db()
    print(f"  БД готова. Запускаю бота...\n")

    bot = Bot(
        token   = token,
        default = DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(dp, bot)

    log.info(f"{BOT_NAME} v{BOT_VERSION} запущен")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        log.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Остановлен.")
