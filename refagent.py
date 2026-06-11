"""
refagent.py — Точка входа RefAgent.

Запуск: python refagent.py

При старте:
  1. Интерактивный ввод токена бота (Enter = оставить из config.json)
  2. Инициализация БД (data/sessions.db)
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
    print(f"\n{'=' * 50}")
    print(f"  {BOT_NAME} v{BOT_VERSION}")
    print(f"{'=' * 50}")

    if existing:
        masked = existing[:8] + "..." + existing[-4:]
        print(f"\n  Текущий токен: {masked}")
        answer = input("  Новый токен (Enter = оставить текущий): ").strip()
        return answer if answer else existing
    else:
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
    from bot.handlers.sessions      import router as sessions_router, set_animator

    animator = Animator(bot)
    set_animator(animator)

    dp.include_router(start_router)
    dp.include_router(sessions_router)   # сессии — до start, чтобы CB_SESSIONS не перехватил placeholder
    dp.include_router(settings_router)


# ════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════

async def main() -> None:
    from tools.db import init_db

    settings = load_settings()
    token    = prompt_token(settings.bot.bot_token)
    settings.bot.bot_token = token
    save_bot_config(settings.bot)
    set_settings(settings)

    print(f"\n  Провайдер: {settings.bot.active_provider}")
    print(f"  Модель:    {settings.bot.active_model or 'по умолчанию'}")
    print(f"\n  Инициализация базы данных...")
    await init_db()
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
