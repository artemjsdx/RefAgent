"""
chat_import.py — Импорт настроек чата из JSON-файла.

Пользователь отправляет .json файл (экспортированный кнопкой 📤 Экспорт).
Бот парсит его и создаёт новый чат с теми же настройками.

Формат файла:
{
  "refagent_chat_export": true,
  "version": 1,
  "name": "Название чата",
  "provider": "openrouter",
  "api_key": "sk-...",
  "api_url": null,
  "model": "deepseek/deepseek-r1-0528:free"
}
"""

from __future__ import annotations

import io
import json
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message

from tools.chat_db import create_chat, PROVIDER_LABELS, PROVIDER_EMOJIS

log    = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════
# РАЗРЕШЁННЫЕ ПРОВАЙДЕРЫ
# ════════════════════════════════════════════════════

ALLOWED_PROVIDERS = {"openrouter", "favoriteapi", "bai"}


# ════════════════════════════════════════════════════
# ХЕНДЛЕР: входящий документ
# ════════════════════════════════════════════════════

@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    """
    Перехватывает любой документ от пользователя.
    Если это валидный экспорт чата — создаёт чат.
    Иначе — молча пропускает (не мешает другим хендлерам обрабатывать файлы).
    """
    doc = message.document

    # Фильтр: только JSON файлы
    is_json = (
        (doc.mime_type and "json" in doc.mime_type)
        or (doc.file_name and doc.file_name.lower().endswith(".json"))
    )
    if not is_json:
        return

    # Скачиваем содержимое файла
    try:
        file_info   = await bot.get_file(doc.file_id)
        buf         = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=buf)
        raw_text    = buf.getvalue().decode("utf-8")
        data        = json.loads(raw_text)
    except Exception as exc:
        log.warning("Ошибка чтения JSON файла: %s", exc)
        await message.answer(
            "❌ Не удалось прочитать файл. Убедись, что это валидный JSON.",
            parse_mode = "HTML",
        )
        return

    # Проверка: это экспорт чата RefAgent?
    if not data.get("refagent_chat_export"):
        # Не экспорт — не трогаем (другие хендлеры могут принять файл)
        return

    # ── Валидация полей ──────────────────────────────

    name     = data.get("name", "").strip()
    provider = data.get("provider", "").strip().lower()
    api_key  = data.get("api_key", "").strip()
    api_url  = data.get("api_url") or None
    model    = data.get("model") or None

    errors = []
    if not name:
        errors.append("• <b>name</b> — пустое или отсутствует")
    if provider not in ALLOWED_PROVIDERS:
        errors.append(f"• <b>provider</b> — неизвестный провайдер «{provider}»")
    if not api_key:
        errors.append("• <b>api_key</b> — пустой или отсутствует")

    if errors:
        await message.answer(
            "❌ <b>Ошибка импорта:</b>\n\n" + "\n".join(errors),
            parse_mode = "HTML",
        )
        return

    # ── Создание чата ────────────────────────────────

    try:
        chat = await create_chat(
            user_id  = message.from_user.id,
            name     = name,
            provider = provider,
            api_key  = api_key,
            api_url  = api_url,
            model    = model,
        )
    except Exception as exc:
        log.error("Ошибка создания импортированного чата: %s", exc)
        await message.answer(
            "❌ Не удалось создать чат. Попробуй ещё раз.",
            parse_mode = "HTML",
        )
        return

    # ── Успех ────────────────────────────────────────

    emoji = PROVIDER_EMOJIS.get(provider, "🤖")
    label = PROVIDER_LABELS.get(provider, provider)

    from bot.keyboards.chat_keyboards import CB_CHAT_OPEN, CB_CHAT_LIST
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    await message.answer(
        f"✅ <b>Чат импортирован!</b>\n\n"
        f"💬 <b>{chat.name}</b>\n"
        f"{emoji} Провайдер: <b>{label}</b>\n"
        f"🧠 Модель: <b>{chat.model or 'по умолчанию'}</b>",
        parse_mode   = "HTML",
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text          = "💬 Открыть чат",
                callback_data = f"{CB_CHAT_OPEN}{chat.id}:enter",
            )],
            [InlineKeyboardButton(
                text          = "📋 К списку чатов",
                callback_data = CB_CHAT_LIST,
            )],
        ]),
    )
