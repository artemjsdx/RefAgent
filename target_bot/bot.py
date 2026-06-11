"""
RefTest Referral Bot — целевой бот для тестирования RefAgent.

Механика «минного поля»:
  1. /start?start=REF_ID — пользователь приходит по рефералке
  2. Проверяем подписку на канал
  3. Если не подписан → кнопка «Подписаться», затем «Проверить»
  4. Если подписан → +1 реферал рефереру, приветствие
  5. /ref   → личная реферальная ссылка
  6. /stats → моя статистика
  7. /top   → топ-5 рефереров

Token:   8901857239:AAGwuUvNQ2iB9ahew4dQ8Ybr2HHvAZTCKno
Channel: -1003703314975  (https://t.me/+7EGLjx54um42ZGQx)
"""

import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.deep_linking import decode_payload

# ── Config ────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("TARGET_BOT_TOKEN", "8901857239:AAGwuUvNQ2iB9ahew4dQ8Ybr2HHvAZTCKno")
CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "-1003703314975"))
CHANNEL_INVITE = "https://t.me/+7EGLjx54um42ZGQx"
DB_PATH    = Path(__file__).parent / "data" / "refs.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("target_bot")

# ── DB ────────────────────────────────────────────────────
def db_init():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            referred_by INTEGER,
            joined_at   REAL DEFAULT (strftime('%s','now')),
            verified    INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referee_id  INTEGER NOT NULL,
            credited_at REAL DEFAULT (strftime('%s','now')),
            UNIQUE(referee_id)
        )
    """)
    conn.commit()
    conn.close()

def db_get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row

def db_upsert_user(user_id, username, first_name, referred_by=None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO users(user_id, username, first_name, referred_by)
        VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name
    """, (user_id, username, first_name, referred_by))
    conn.commit()
    conn.close()

def db_credit_referral(referrer_id: int, referee_id: int) -> bool:
    """Записать реферал. Вернуть True если новый."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO referrals(referrer_id, referee_id) VALUES(?,?)",
            (referrer_id, referee_id)
        )
        conn.execute(
            "UPDATE users SET verified=1 WHERE user_id=?", (referee_id,)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def db_ref_count(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    n = conn.execute(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return n

def db_top(limit=5):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT r.referrer_id, u.first_name, u.username, COUNT(*) as cnt
        FROM referrals r LEFT JOIN users u ON u.user_id = r.referrer_id
        GROUP BY r.referrer_id ORDER BY cnt DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows

# ── Keyboards ────────────────────────────────────────────
def kb_subscribe(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_INVITE),
        InlineKeyboardButton(text="✅ Проверить подписку",   callback_data=f"check:{user_id}"),
    ]])

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Моя рефералка", callback_data="myref")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats"),
         InlineKeyboardButton(text="🏆 Топ-5",          callback_data="top")],
    ])

# ── Helpers ──────────────────────────────────────────────
async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        log.info(f"Subscription check uid={user_id} status={member.status}")
        return member.status not in ("left", "kicked", "banned")
    except Exception as e:
        log.error(f"Subscription check FAILED for uid={user_id}: {type(e).__name__}: {e}")
        # If bot can't check — deny by default (security)
        return False

def ref_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start={user_id}"

# ── Handlers ─────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    user = msg.from_user
    payload = msg.text.split(maxsplit=1)[1] if len(msg.text.split()) > 1 else ""

    # Убираем "start=" если передан через deep link
    if payload.startswith("start="):
        payload = payload[6:]

    referred_by = int(payload) if payload.isdigit() and int(payload) != user.id else None

    db_upsert_user(user.id, user.username, user.first_name, referred_by)

    # Проверяем подписку
    if not await is_subscribed(bot, user.id):
        await msg.answer(
            f"👋 Привет, <b>{user.first_name}</b>!\n\n"
            f"Чтобы участвовать в реферальной программе, нужно подписаться на наш канал.\n\n"
            f"<b>Шаги:</b>\n"
            f"1️⃣ Нажми «Подписаться на канал»\n"
            f"2️⃣ Нажми «Проверить подписку»",
            parse_mode="HTML",
            reply_markup=kb_subscribe(user.id),
        )
        return

    # Уже подписан — кредитуем реферал
    await _welcome_verified(msg, user, referred_by)


async def _welcome_verified(msg_or_cb, user, referred_by):
    is_new_ref = False
    if referred_by:
        is_new_ref = db_credit_referral(referred_by, user.id)

    ref_text = ""
    if is_new_ref:
        cnt = db_ref_count(referred_by)
        ref_text = f"\n\n✅ Реферал засчитан! У пригласившего теперь <b>{cnt}</b> рефералов."

    me = await bot.get_me()
    my_link = ref_link(me.username, user.id)
    my_cnt  = db_ref_count(user.id)

    text = (
        f"🎉 Добро пожаловать, <b>{user.first_name}</b>!{ref_text}\n\n"
        f"🔗 Твоя реферальная ссылка:\n<code>{my_link}</code>\n\n"
        f"👥 Твоих рефералов: <b>{my_cnt}</b>"
    )
    send = msg_or_cb.message.answer if isinstance(msg_or_cb, CallbackQuery) else msg_or_cb.answer
    await send(text, parse_mode="HTML", reply_markup=kb_main())


@dp.callback_query(F.data.startswith("check:"))
async def cb_check_sub(cb: CallbackQuery):
    user = cb.from_user
    if not await is_subscribed(bot, user.id):
        await cb.answer("❌ Ты ещё не подписался!", show_alert=True)
        return

    await cb.answer("✅ Подписка подтверждена!")
    row = db_get_user(user.id)
    referred_by = row[3] if row else None  # referred_by column
    await _welcome_verified(cb, user, referred_by)


@dp.callback_query(F.data == "myref")
async def cb_myref(cb: CallbackQuery):
    me = await bot.get_me()
    link = ref_link(me.username, cb.from_user.id)
    await cb.message.answer(
        f"🔗 Твоя реферальная ссылка:\n<code>{link}</code>",
        parse_mode="HTML",
    )
    await cb.answer()


@dp.callback_query(F.data == "stats")
async def cb_stats(cb: CallbackQuery):
    cnt = db_ref_count(cb.from_user.id)
    await cb.message.answer(f"📊 Твоих рефералов: <b>{cnt}</b>", parse_mode="HTML")
    await cb.answer()


@dp.callback_query(F.data == "top")
async def cb_top(cb: CallbackQuery):
    rows = db_top()
    if not rows:
        await cb.message.answer("Пока нет рефералов 🤷")
    else:
        lines = []
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
        for i, (uid, fname, uname, cnt) in enumerate(rows):
            name = f"@{uname}" if uname else (fname or str(uid))
            lines.append(f"{medals[i]} {name} — <b>{cnt}</b>")
        await cb.message.answer("🏆 Топ рефереров:\n\n" + "\n".join(lines), parse_mode="HTML")
    await cb.answer()


@dp.message(Command("ref"))
async def cmd_ref(msg: Message):
    me = await bot.get_me()
    link = ref_link(me.username, msg.from_user.id)
    await msg.answer(f"🔗 Твоя рефералка:\n<code>{link}</code>", parse_mode="HTML")


@dp.message(Command("stats"))
async def cmd_stats(msg: Message):
    cnt = db_ref_count(msg.from_user.id)
    await msg.answer(f"📊 Рефералов: <b>{cnt}</b>", parse_mode="HTML")


@dp.message(Command("top"))
async def cmd_top(msg: Message):
    rows = db_top()
    if not rows:
        await msg.answer("Пока нет рефералов 🤷")
        return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    lines = []
    for i, (uid, fname, uname, cnt) in enumerate(rows):
        name = f"@{uname}" if uname else (fname or str(uid))
        lines.append(f"{medals[i]} {name} — <b>{cnt}</b>")
    await msg.answer("🏆 Топ рефереров:\n\n" + "\n".join(lines), parse_mode="HTML")


# ── Main ─────────────────────────────────────────────────
async def main():
    db_init()
    log.info("RefTest Referral Bot starting...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
