"""
conductor_tools.py — Harold Conductor Pattern для RefAgent.

ПОЧЕМУ Harold:
  - 0% аккаунтов могут напрямую написать боту без общего диалога
  - Conductor (проводник) создаёт временную группу, добавляет бота
  - Рефаккаунты вступают в группу через invite-ссылку
  - Это создаёт общий контекст: теперь аккаунты могут писать боту

ЦИКЛ:
  1. conductor_setup(bot_username) → {group_id, invite_link}
  2. conductor_join_group(account_id, invite_link) — для каждого аккаунта
  3. [агент работает с ботом]
  4. conductor_cleanup(group_id) — удалить временную группу

КРИТИЧНО:
  - invite_link может содержать дефис: t.me/+AbCd-EfGh_IjKl
  - Regex для хеша: r"[A-Za-z0-9_-]+"
  - Проводник должен быть назначен в базе (is_conductor=True)
"""

from __future__ import annotations

import re
import asyncio
from typing import Optional

from telethon.tl.functions.channels import (
    CreateChannelRequest, DeleteChannelRequest,
    InviteToChannelRequest, ExportMessageLinkRequest,
)
from telethon.tl.functions.messages import ExportChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import InputPeerChannel

from tools.db import get_conductor
from tools.tg_tools import _get_client, join_channel


# ════════════════════════════════════════════════════
# INVITE LINK REGEX
# ════════════════════════════════════════════════════

# Invite hash может содержать дефис: t.me/+AbCd-EfGh или t.me/joinchat/AbCd
INVITE_HASH_RE = re.compile(r"t\.me/(?:\+|joinchat/)([A-Za-z0-9_-]+)")


def extract_invite_hash(link: str) -> Optional[str]:
    """
    Извлечь hash из invite-ссылки.
    Поддерживает t.me/+HASH и t.me/joinchat/HASH (включая дефис в хеше).
    """
    m = INVITE_HASH_RE.search(link)
    return m.group(1) if m else None


# ════════════════════════════════════════════════════
# CONDUCTOR SETUP
# ════════════════════════════════════════════════════

async def conductor_setup(bot_username: str) -> dict:
    """
    Создать временную группу через проводника, добавить бота.

    Returns:
        {ok, group_id, invite_link, error?}
    """
    conductor = await get_conductor()
    if not conductor:
        return {"ok": False, "error": "Проводник не назначен. Назначь проводника в меню Сессии."}

    try:
        client = await _get_client(conductor.id)

        # Создать временную группу
        group_name = f"_ref_{bot_username[:20]}_{int(asyncio.get_event_loop().time()) % 100000}"
        result     = await client(CreateChannelRequest(
            title     = group_name,
            about     = "Temp group",
            megagroup = True,
        ))
        channel    = result.chats[0]
        group_id   = channel.id

        # Добавить бота в группу
        try:
            bot_entity = await client.get_entity(bot_username.lstrip("@"))
            await client(InviteToChannelRequest(channel, [bot_entity]))
        except Exception as e:
            # Некоторые боты нельзя добавить напрямую — продолжаем
            pass

        # Получить invite-ссылку
        invite_result = await client(ExportChatInviteRequest(channel))
        invite_link   = invite_result.link

        return {
            "ok":          True,
            "group_id":    group_id,
            "group_name":  group_name,
            "invite_link": invite_link,
            "conductor_id": conductor.id,
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════
# JOIN GROUP (Harold step for referral accounts)
# ════════════════════════════════════════════════════

async def conductor_join_group(account_id: int, invite_link: str) -> dict:
    """
    Аккаунт вступает в группу проводника по invite-ссылке.
    Это создаёт общий контекст с ботом — Harold pattern.
    """
    return await join_channel(account_id, invite_link)


# ════════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════════

async def conductor_cleanup(group_id: int) -> dict:
    """
    Удалить временную группу проводника.
    Вызывается после завершения задачи.
    """
    conductor = await get_conductor()
    if not conductor:
        return {"ok": False, "error": "Проводник не назначен"}

    try:
        client  = await _get_client(conductor.id)
        channel = await client.get_entity(group_id)
        await client(DeleteChannelRequest(channel))
        return {"ok": True, "group_id": group_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
