"""
starfall_blast.py — Параллельная накрутка рефералов для @starfalll_tg_bot.

Паттерн из covet.txt (доказан: 15+ рефов засчитано):
  1. 4 бота с param (4с между каждым)
  2. Пауза 15с
  3. MNGFwuq4aJZjMzFi ПЕРВЫМ (ImportChatInviteRequest) + 35с
  4. yn9pG8S1lH (JoinChannelRequest, открытый) + 35с
  5. 4 approval-канала по 35с (8ngTVv последний → FloodWait ~125с, ждём и ретраим)
  6. Пауза 10с
  7. Verify: StartBotRequest → читаем 3 сообщения

ПРАВИЛА:
  - Каждый аккаунт = свой api_id/api_hash из .json сайдкара
  - CONCURRENCY = все аккаунты сразу (FloodWait у каждого свой, не суммируется)
  - InviteRequestSentError = УСПЕХ для approval-каналов
  - MAX_FLOOD_WAIT = 600с (если больше — пропустить канал)
  - Кондуктор +14707526421 и +14707620517 — не трогать
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    UserAlreadyParticipantError,
    InviteHashExpiredError,
    InviteRequestSentError,
    ChannelPrivateError,
    UserBannedInChannelError,
    UserDeactivatedBanError,
    AuthKeyUnregisteredError,
)
from telethon.tl.functions.messages import ImportChatInviteRequest, StartBotRequest
from telethon.tl.functions.channels import JoinChannelRequest


# ════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════

SESSIONS_DIR   = Path(__file__).parent / "data" / "sessions"
TARGET_BOT     = "starfalll_tg_bot"
REF_PARAM      = "bEIrpUnDF8HoZo"       # param для /start — реф-ссылка кондуктора
VERIFY_TEXT    = "Не забывай забирать ежедневный бонус"  # признак успеха

# Аккаунты-кондукторы — НИКОГДА не использовать для рефов
CONDUCTOR_PHONES = {"+14707526421", "+14707620517"}

# Задержки (секунды)
DELAY_BETWEEN_BOTS     = 4
DELAY_AFTER_BOTS       = 15
DELAY_AFTER_CHANNEL    = 35
DELAY_BEFORE_VERIFY    = 10
MAX_FLOOD_WAIT         = 600   # если FloodWait > этого — пропускаем канал

# Дефолтные API credentials (Telegram Desktop — не палится)
DEFAULT_API_ID   = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"
SYSTEM_VERSION   = "4.16.30-vxCUSTOM"

# Паттерн: 4 бота-спонсора (в порядке вызова)
SPONSOR_BOTS = [
    "vkm6bot",
    "freegiftro_bot",
    "Ruletkaa_Chat_Bot",
    "Muzika_slux_bot",
]

# Паттерн: каналы для вступления (MNGF ПЕРВЫМ — критично!)
PRIVATE_CHANNELS = [
    "MNGFwuq4aJZjMzFi",    # ImportChatInviteRequest — ВСЕГДА ПЕРВЫМ
    "GnveFlDjTBlhMmFi",    # approval → InviteRequestSentError = УСПЕХ
    "zFkpEaV-cj83MzFi",    # approval
    "YxWpUqar3T5hMmFi",    # approval
    "8ngTVvUUbHthMmFi",    # approval — FloodWait ~125с, ждём!
]

# Открытый канал (JoinChannelRequest, не ImportChatInviteRequest)
OPEN_CHANNEL = "yn9pG8S1lH"


# ════════════════════════════════════════════════════
# SESSION DISCOVERY
# ════════════════════════════════════════════════════

def load_sidecar(session_path: Path) -> tuple[int, str]:
    """Читаем .json сайдкар рядом с .session — берём app_id и app_hash."""
    json_path = session_path.with_suffix(".json")
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
            return int(data["app_id"]), str(data["app_hash"])
        except Exception:
            pass
    return DEFAULT_API_ID, DEFAULT_API_HASH


def discover_sessions() -> list[tuple[str, Path]]:
    """
    Найти все .session файлы в SESSIONS_DIR.
    Пропускаем: кондукторов, дубликаты (с (1)), числовые (239913XXX_telethon).
    Возвращаем: [(phone, session_path), ...]
    """
    sessions = []
    for sp in sorted(SESSIONS_DIR.glob("*.session")):
        name = sp.stem  # например +14707526481

        # Пропускаем числовые сессии без телефона
        if "_telethon" in name:
            print(f"  ⏭  Пропускаю числовую сессию: {sp.name}")
            continue

        # Пропускаем дубликаты " (1)"
        if "(1)" in name or "copy" in name.lower():
            print(f"  ⏭  Пропускаю дубликат: {sp.name}")
            continue

        phone = name  # "+14707526481"

        # Пропускаем кондукторов
        if phone in CONDUCTOR_PHONES:
            print(f"  🔒 Кондуктор — пропускаю: {phone}")
            continue

        sessions.append((phone, sp))

    return sessions


# ════════════════════════════════════════════════════
# CORE: ОДИН АККАУНТ
# ════════════════════════════════════════════════════

async def join_private(client: TelegramClient, hash_: str) -> str:
    """
    ImportChatInviteRequest с обработкой FloodWait и уже-участника.
    Возвращает: "joined" | "already" | "request_sent" | "flood_too_long:{N}" | "error:{msg}"
    """
    for attempt in range(3):
        try:
            await client(ImportChatInviteRequest(hash_))
            return "joined"
        except UserAlreadyParticipantError:
            return "already"
        except InviteRequestSentError:
            return "request_sent"    # approval-канал — это УСПЕХ
        except FloodWaitError as e:
            wait = e.seconds
            if wait > MAX_FLOOD_WAIT:
                return f"flood_too_long:{wait}"
            print(f"      ⏱  FloodWait {wait}с на hash={hash_[:8]}... — жду")
            await asyncio.sleep(wait + 3)
            # retry
        except (InviteHashExpiredError, ChannelPrivateError) as e:
            return f"error:{type(e).__name__}"
        except Exception as e:
            return f"error:{str(e)[:60]}"
    return "error:max_retries"


async def join_open(client: TelegramClient, username: str) -> str:
    """
    JoinChannelRequest для открытого канала.
    Возвращает: "joined" | "already" | "flood_too_long:{N}" | "error:{msg}"
    """
    for attempt in range(3):
        try:
            entity = await client.get_entity(username)
            await client(JoinChannelRequest(entity))
            return "joined"
        except UserAlreadyParticipantError:
            return "already"
        except FloodWaitError as e:
            wait = e.seconds
            if wait > MAX_FLOOD_WAIT:
                return f"flood_too_long:{wait}"
            print(f"      ⏱  FloodWait {wait}с на @{username} — жду")
            await asyncio.sleep(wait + 3)
        except UserBannedInChannelError:
            return "error:UserBannedInChannel"
        except Exception as e:
            return f"error:{str(e)[:60]}"
    return "error:max_retries"


async def start_bot_with_param(client: TelegramClient, bot: str, param: str) -> str:
    """StartBotRequest с реф-параметром."""
    try:
        bot_entity = await client.get_entity(bot)
        await client(StartBotRequest(bot=bot_entity, peer=bot_entity, start_param=param))
        return "ok"
    except FloodWaitError as e:
        if e.seconds <= MAX_FLOOD_WAIT:
            await asyncio.sleep(e.seconds + 3)
            try:
                bot_entity = await client.get_entity(bot)
                await client(StartBotRequest(bot=bot_entity, peer=bot_entity, start_param=param))
                return "ok_retry"
            except Exception:
                pass
        return f"flood:{e.seconds}"
    except Exception as e:
        return f"error:{str(e)[:60]}"


async def verify_referral(client: TelegramClient) -> bool:
    """Проверить что реф засчитан: читаем 3 последних сообщения от бота."""
    try:
        bot_entity = await client.get_entity(TARGET_BOT)
        msgs = await client.get_messages(bot_entity, limit=3)
        for m in msgs:
            if m.text and VERIFY_TEXT in m.text:
                return True
    except Exception:
        pass
    return False


async def process_account(
    phone: str,
    session_path: Path,
    sem: asyncio.Semaphore,
    results: dict,
) -> None:
    """Полный паттерн для одного аккаунта. Запускается параллельно."""

    async with sem:
        api_id, api_hash = load_sidecar(session_path)
        client = TelegramClient(
            str(session_path.with_suffix("")),
            api_id,
            api_hash,
            system_version=SYSTEM_VERSION,
        )

        log_lines = []

        def log(msg: str) -> None:
            ts = time.strftime("%H:%M:%S")
            line = f"  [{phone}] {msg}"
            log_lines.append(f"{ts} {line}")
            print(line)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                log("❌ Не авторизован — пропускаю")
                results[phone] = {"ok": False, "reason": "unauthorized"}
                return

            me = await client.get_me()
            log(f"✅ Подключён uid={me.id} name={me.first_name}")

            # ── Шаг 1: 4 бота-спонсора ──────────────────────────
            log("→ Шаг 1: Запускаю 4 спонсорских бота")
            for bot_name in SPONSOR_BOTS:
                status = await start_bot_with_param(client, bot_name, REF_PARAM)
                log(f"  bot={bot_name} → {status}")
                await asyncio.sleep(DELAY_BETWEEN_BOTS)

            # ── Шаг 2: Пауза ────────────────────────────────────
            log(f"→ Шаг 2: Пауза {DELAY_AFTER_BOTS}с")
            await asyncio.sleep(DELAY_AFTER_BOTS)

            # ── Шаг 3: MNGFwuq ПЕРВЫМ ───────────────────────────
            mngf_hash = PRIVATE_CHANNELS[0]
            log(f"→ Шаг 3: MNGF первым hash={mngf_hash[:8]}...")
            r = await join_private(client, mngf_hash)
            log(f"  MNGF → {r}")
            await asyncio.sleep(DELAY_AFTER_CHANNEL)

            # ── Шаг 4: Открытый канал ────────────────────────────
            log(f"→ Шаг 4: Открытый канал @{OPEN_CHANNEL}")
            r = await join_open(client, OPEN_CHANNEL)
            log(f"  open → {r}")
            await asyncio.sleep(DELAY_AFTER_CHANNEL)

            # ── Шаг 5: 4 approval-канала ─────────────────────────
            log("→ Шаг 5: 4 approval-канала")
            approval_results = []
            for ch_hash in PRIVATE_CHANNELS[1:]:
                r = await join_private(client, ch_hash)
                log(f"  approval hash={ch_hash[:8]}... → {r}")
                approval_results.append(r)
                await asyncio.sleep(DELAY_AFTER_CHANNEL)

            # ── Шаг 6: Финальная пауза ───────────────────────────
            log(f"→ Шаг 6: Пауза {DELAY_BEFORE_VERIFY}с перед verify")
            await asyncio.sleep(DELAY_BEFORE_VERIFY)

            # ── Шаг 7: Verify ────────────────────────────────────
            log("→ Шаг 7: Verify — StartBotRequest к starfalll_tg_bot")
            v_status = await start_bot_with_param(client, TARGET_BOT, REF_PARAM)
            log(f"  start → {v_status}")
            await asyncio.sleep(5)
            success = await verify_referral(client)

            if success:
                log("🎉 РЕФЕРАЛ ЗАСЧИТАН!")
                results[phone] = {"ok": True, "reason": "verified"}
            else:
                log("⚠️  Verify не подтвердил — возможно засчитается позже")
                results[phone] = {"ok": True, "reason": "steps_done_verify_unclear"}

        except UserDeactivatedBanError:
            log("❌ Аккаунт забанен")
            results[phone] = {"ok": False, "reason": "banned"}
        except AuthKeyUnregisteredError:
            log("❌ Сессия устарела")
            results[phone] = {"ok": False, "reason": "session_expired"}
        except Exception as e:
            log(f"❌ Ошибка: {e}")
            results[phone] = {"ok": False, "reason": str(e)[:100]}
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass


# ════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════

async def main() -> None:
    sessions = discover_sessions()

    if not sessions:
        print("❌ Сессии не найдены в", SESSIONS_DIR)
        sys.exit(1)

    n = len(sessions)
    print(f"\n{'═'*60}")
    print(f"  Starfall Referral Blast")
    print(f"  Бот:        @{TARGET_BOT}")
    print(f"  Параметр:   {REF_PARAM}")
    print(f"  Аккаунтов:  {n} (все параллельно)")
    print(f"  ~Время:     7-8 мин (FloodWait у каждого свой)")
    print(f"{'═'*60}\n")

    results: dict = {}
    # CONCURRENCY = все аккаунты сразу (FloodWait'ы не суммируются!)
    sem = asyncio.Semaphore(n)

    tasks = [
        process_account(phone, sp, sem, results)
        for phone, sp in sessions
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    # ── Итоговый отчёт ───────────────────────────────
    print(f"\n{'═'*60}")
    print("  ИТОГ")
    print(f"{'═'*60}")
    verified  = sum(1 for r in results.values() if r.get("ok") and r.get("reason") == "verified")
    done      = sum(1 for r in results.values() if r.get("ok"))
    failed    = sum(1 for r in results.values() if not r.get("ok"))

    for phone, r in sorted(results.items()):
        mark = "🎉" if r.get("reason") == "verified" else ("✅" if r.get("ok") else "❌")
        print(f"  {mark}  {phone:<18} {r.get('reason','')}")

    print(f"\n  Всего аккаунтов:  {n}")
    print(f"  Шаги выполнены:   {done}")
    print(f"  Verify подтверждён: {verified}")
    print(f"  Ошибок:           {failed}")
    print(f"\n  ⏰ Реф может засчитаться через 1-5 мин после verify")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
