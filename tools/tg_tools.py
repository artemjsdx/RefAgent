"""
tg_tools.py — Telegram-инструменты на базе Telethon.

Инструменты для агента:
  connect_account     — подключить аккаунт по ID
  disconnect_account  — отключить аккаунт
  join_channel        — вступить в канал/группу
  start_bot           — /start боту (с deeplink)
  send_message        — отправить сообщение
  get_messages        — получить последние сообщения
  click_button        — нажать inline-кнопку
  wait_bot_response   — дождаться ответа бота

КРИТИЧНО:
  - Каждый аккаунт имеет уникальные api_id + api_hash из sidecar .json
  - random_id: int.from_bytes(os.urandom(8), 'big', signed=True) — никогда 0
  - Harold pattern: бот должен быть в общей группе перед DM
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    UserDeactivatedBanError,
    AuthKeyUnregisteredError,
    ChatAdminRequiredError,
    InviteHashExpiredError,
    PeerIdInvalidError,
    ChannelPrivateError,
    FloodWaitError,
)
from telethon.tl.functions.messages import ImportChatInviteRequest, GetHistoryRequest
from telethon.tl.functions.channels import JoinChannelRequest

from config.constants import (
    TIMING_BOT_RESPONSE, TIMING_BOT_RESPONSE_RETRY,
    TIMING_BOT_MAX_ATTEMPTS,
)
from tools.db import get_account


# ════════════════════════════════════════════════════
# CLIENT POOL
# ════════════════════════════════════════════════════

_clients: dict[int, TelegramClient] = {}


def _safe_random_id() -> int:
    rid = 0
    while rid == 0:
        rid = int.from_bytes(os.urandom(8), "big", signed=True)
    return rid


async def _get_client(account_id: int) -> TelegramClient:
    """Вернуть подключённый клиент из пула или создать новый."""
    if account_id in _clients:
        client = _clients[account_id]
        if client.is_connected():
            return client
        await client.disconnect()
        del _clients[account_id]

    acc = await get_account(account_id)
    if not acc:
        raise ValueError(f"Аккаунт {account_id} не найден в базе")

    session_path = Path(acc.session_path)
    if not session_path.exists():
        raise FileNotFoundError(f"Файл сессии не найден: {session_path}")

    client = TelegramClient(
        str(session_path.with_suffix("")),
        api_id   = acc.api_id,
        api_hash = acc.api_hash,
    )
    try:
        await client.connect()
    except ValueError as e:
        err = str(e)
        if "unpack" in err:
            raise ValueError(
                f"Сессия {session_path.name} несовместима с текущей версией Telethon "
                f"(структура таблицы sessions отличается). "
                f"Пересоздай сессию через: python -m telethon.sessions {session_path.stem}"
            ) from e
        raise
    _clients[account_id] = client
    return client


# ════════════════════════════════════════════════════
# CONNECT / DISCONNECT
# ════════════════════════════════════════════════════

async def connect_account(account_id: int) -> dict:
    """
    Подключить аккаунт и вернуть базовую информацию.
    """
    try:
        client = await _get_client(account_id)
        me     = await client.get_me()
        if not me:
            return {"ok": False, "error": "Не удалось получить информацию об аккаунте"}

        return {
            "ok":       True,
            "uid":      me.id,
            "phone":    me.phone,
            "username": me.username,
            "first_name": me.first_name,
        }
    except UserDeactivatedBanError:
        return {"ok": False, "error": "Аккаунт забанен (UserDeactivatedBan)"}
    except AuthKeyUnregisteredError:
        return {"ok": False, "error": "Сессия устарела (AuthKeyUnregistered)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def disconnect_account(account_id: int) -> dict:
    """Отключить аккаунт и удалить из пула."""
    client = _clients.pop(account_id, None)
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass
    return {"ok": True}


async def disconnect_all() -> None:
    """Отключить все активные клиенты. Вызывается при остановке агента."""
    for account_id, client in list(_clients.items()):
        try:
            await client.disconnect()
        except Exception:
            pass
    _clients.clear()


# ════════════════════════════════════════════════════
# JOIN CHANNEL
# ════════════════════════════════════════════════════

async def join_channel(account_id: int, link: str) -> dict:
    """
    Вступить в канал/группу.
    link: @username, t.me/+HASH (private invite), t.me/joinchat/HASH
    """
    try:
        client = await _get_client(account_id)

        # Определить тип ссылки
        if "+joinchat/" in link or "/joinchat/" in link or "t.me/+" in link:
            # Приватная invite-ссылка
            hash_part = link.split("/")[-1].lstrip("+")
            await client(ImportChatInviteRequest(hash_part))
        else:
            # Публичный канал/группа
            entity = await client.get_entity(link.lstrip("@"))
            await client(JoinChannelRequest(entity))

        return {"ok": True, "link": link}

    except InviteHashExpiredError:
        return {"ok": False, "error": "InviteHashExpired — ссылка устарела или исчерпана"}
    except ChannelPrivateError:
        return {"ok": False, "error": "ChannelPrivate — канал закрыт"}
    except FloodWaitError as e:
        return {"ok": False, "error": f"FloodWait {e.seconds}с"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════
# START BOT
# ════════════════════════════════════════════════════

async def start_bot(
    account_id:   int,
    bot_username: str,
    start_param:  Optional[str] = None,
) -> dict:
    """
    Отправить /start боту.
    HAROLD PATTERN: бот должен быть в общей группе!
    start_param: deeplink параметр из реф-ссылки
    """
    try:
        client = await _get_client(account_id)
        bot    = await client.get_entity(bot_username.lstrip("@"))

        if start_param:
            await client.send_message(bot, f"/start {start_param}")
        else:
            await client.send_message(bot, "/start")

        return {"ok": True, "bot": bot_username, "param": start_param}

    except PeerIdInvalidError:
        return {
            "ok":    False,
            "error": "PeerIdInvalid — Harold pattern: нужна общая группа с ботом перед отправкой",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════
# SEND MESSAGE
# ════════════════════════════════════════════════════

async def send_message(account_id: int, peer: str, text: str) -> dict:
    """Отправить текстовое сообщение."""
    try:
        client = await _get_client(account_id)
        entity = await client.get_entity(peer)
        msg    = await client.send_message(entity, text)
        return {"ok": True, "message_id": msg.id}
    except PeerIdInvalidError:
        return {"ok": False, "error": "PeerIdInvalid — нет общей группы с этим пользователем"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════
# GET MESSAGES
# ════════════════════════════════════════════════════

async def get_messages(account_id: int, peer: str, limit: int = 5) -> dict:
    """Получить последние сообщения из диалога."""
    try:
        from telethon.tl.types import KeyboardButtonUrl
        client   = await _get_client(account_id)
        entity   = await client.get_entity(peer)
        messages = await client.get_messages(entity, limit=limit)
        result   = []
        for m in messages:
            entry: dict = {
                "id":      m.id,
                "date":    m.date.isoformat() if m.date else None,
                "text":    m.message or "",
                "out":     m.out,
                "buttons": [],
            }
            if m.buttons:
                rows = []
                for row in m.buttons:
                    r = []
                    for btn in row:
                        b: dict = {"text": btn.text}
                        raw = getattr(btn, "button", None)
                        if isinstance(raw, KeyboardButtonUrl):
                            b["url"] = raw.url
                        r.append(b)
                    rows.append(r)
                entry["buttons"] = rows
            result.append(entry)
        return {"ok": True, "messages": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_inline_button_urls(
    account_id: int,
    peer:       str,
    message_id: int,
) -> dict:
    """
    Вернуть список URL-кнопок из сообщения (KeyboardButtonUrl).
    Используй для извлечения ссылок на каналы перед join_channel.
    """
    try:
        from telethon.tl.types import KeyboardButtonUrl, KeyboardButtonCallback
        client  = await _get_client(account_id)
        entity  = await client.get_entity(peer)
        message = await client.get_messages(entity, ids=message_id)

        if not message or not message.buttons:
            return {"ok": False, "error": "Сообщение не найдено или нет кнопок"}

        url_buttons      = []
        callback_buttons = []
        for row in message.buttons:
            for btn in row:
                raw = getattr(btn, "button", None)
                if isinstance(raw, KeyboardButtonUrl):
                    url_buttons.append({"text": btn.text, "url": raw.url})
                elif isinstance(raw, KeyboardButtonCallback):
                    callback_buttons.append({"text": btn.text})

        return {
            "ok":               True,
            "url_buttons":      url_buttons,
            "callback_buttons": callback_buttons,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════
# CLICK BUTTON
# ════════════════════════════════════════════════════

async def click_button(
    account_id:  int,
    peer:        str,
    message_id:  int,
    button_text: Optional[str] = None,
    row:         int           = 0,
    col:         int           = 0,
) -> dict:
    """Нажать inline-кнопку в сообщении."""
    try:
        client  = await _get_client(account_id)
        entity  = await client.get_entity(peer)
        message = await client.get_messages(entity, ids=message_id)

        if not message or not message.buttons:
            return {"ok": False, "error": "Сообщение не найдено или нет кнопок"}

        # Найти кнопку по тексту или координатам
        if button_text:
            for r in message.buttons:
                for btn in r:
                    if btn.text == button_text:
                        await btn.click()
                        return {"ok": True, "clicked": btn.text}
            return {"ok": False, "error": f"Кнопка '{button_text}' не найдена"}
        else:
            btn_rows = message.buttons
            if row < len(btn_rows) and col < len(btn_rows[row]):
                btn = btn_rows[row][col]
                await btn.click()
                return {"ok": True, "clicked": btn.text}
            return {"ok": False, "error": f"Кнопка [{row}][{col}] не существует"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════
# WAIT BOT RESPONSE
# ════════════════════════════════════════════════════

async def wait_bot_response(
    account_id: int,
    peer:       str,
    timeout:    int = TIMING_BOT_RESPONSE,
) -> dict:
    """
    Дождаться нового сообщения от бота после действия.
    Сравнивает ID последнего сообщения перед ожиданием.
    """
    try:
        client     = await _get_client(account_id)
        entity     = await client.get_entity(peer)
        before_msgs = await client.get_messages(entity, limit=1)
        last_id     = before_msgs[0].id if before_msgs else 0

        deadline     = asyncio.get_event_loop().time() + timeout
        attempts     = 0
        max_attempts = TIMING_BOT_MAX_ATTEMPTS

        while asyncio.get_event_loop().time() < deadline and attempts < max_attempts:
            await asyncio.sleep(TIMING_BOT_RESPONSE_RETRY)
            new_msgs = await client.get_messages(entity, limit=3)
            fresh    = [m for m in new_msgs if m.id > last_id and not m.out]
            if fresh:
                result = []
                for m in fresh:
                    entry: dict = {
                        "id":   m.id,
                        "text": m.message or "",
                        "buttons": [],
                    }
                    if m.buttons:
                        entry["buttons"] = [[btn.text for btn in row] for row in m.buttons]
                    result.append(entry)
                return {"ok": True, "messages": result}
            attempts += 1

        return {"ok": False, "error": f"Бот не ответил за {timeout}с"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
