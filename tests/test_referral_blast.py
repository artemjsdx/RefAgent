"""
test_referral_blast.py — Автономный тест реферальной накрутки.

Сценарий:
  Проводник +14707620517 (uid=8978062324) опубликовал ссылку.
  3 рефагент-аккаунта (+14707526421, +14707526481, +14707526490)
  последовательно:
    1. Открывают бота @RefTestRef8483_bot?start=8978062324
    2. Подписываются на канал -1003703314975
    3. Нажимают «Проверить подписку»
  После — проверяем /stats в target_bot DB.

Задержки: TIMING_BETWEEN_ACCOUNTS между аккаунтами.
"""
import asyncio, sys, os, json, time, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telethon import TelegramClient
from telethon.tl.types import KeyboardButtonCallback

SESSIONS_DIR = Path("data/sessions")
TARGET_BOT   = "RefTestRef8483_bot"
CHANNEL_ID   = -1003703314975
CHANNEL_LINK = "https://t.me/+7EGLjx54um42ZGQx"
CONDUCTOR_UID = 8978062324
START_PARAM  = str(CONDUCTOR_UID)
WAIT_BETWEEN = 20   # секунд между аккаунтами
TARGET_BOT_DB = Path("target_bot/data/refs.db")

REFAGENT_ACCOUNTS = [
    ("+14707526421", "data/sessions/+14707526421_1781218518023.session"),
    ("+14707526481", "data/sessions/+14707526481_1781218518059.session"),
    ("+14707526490", "data/sessions/+14707526490_1781218518080.session"),
]
API_ID   = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"


def db_ref_count(uid: int) -> int:
    if not TARGET_BOT_DB.exists():
        return -1
    conn = sqlite3.connect(TARGET_BOT_DB)
    n = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,)).fetchone()[0]
    conn.close()
    return n


async def do_referral(phone: str, session_path: str) -> bool:
    print(f"\n  ▶ [{phone}] Подключаюсь...")
    client = TelegramClient(session_path.replace(".session",""), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"  ❌ [{phone}] Не авторизован")
            return False

        me = await client.get_me()
        print(f"  ✅ [{phone}] Подключён — uid={me.id} name={me.first_name}")

        # 1. Подписаться на канал через invite link hash напрямую
        print(f"  📢 [{phone}] Подписываюсь на канал...")
        try:
            from telethon.tl.functions.messages import ImportChatInviteRequest
            invite_hash = CHANNEL_LINK.split("/+")[1]
            await client(ImportChatInviteRequest(invite_hash))
            print(f"  ✅ [{phone}] Подписался на канал")
        except Exception as e:
            err = str(e)
            if "already" in err.lower() or "USER_ALREADY" in err or "INVITE_REQUEST" in err:
                print(f"  ℹ️  [{phone}] Уже подписан / заявка отправлена")
            else:
                print(f"  ⚠️  [{phone}] Join канал: {e}")

        await asyncio.sleep(2)

        # 2. Открыть бота с реф-ссылкой
        print(f"  🤖 [{phone}] Открываю бота со start={START_PARAM}...")
        bot = await client.get_entity(TARGET_BOT)
        from telethon.tl.functions.messages import StartBotRequest
        await client(StartBotRequest(
            bot=bot,
            peer=bot,
            start_param=START_PARAM
        ))
        await asyncio.sleep(3)

        # 3. Получить последнее сообщение бота и нажать «Проверить подписку»
        msgs = await client.get_messages(bot, limit=5)
        clicked = False
        for msg in msgs:
            if not msg.reply_markup:
                continue
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, 'data') and b'check' in btn.data:
                        print(f"  🖱  [{phone}] Нажимаю «Проверить подписку»...")
                        await msg.click(data=btn.data)
                        clicked = True
                        break
                if clicked:
                    break
            if clicked:
                break

        if not clicked:
            # Ищем кнопку по тексту
            for msg in msgs:
                if not msg.reply_markup:
                    continue
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        text = getattr(btn, 'text', '')
                        if 'проверить' in text.lower() or 'check' in text.lower() or '✅' in text:
                            print(f"  🖱  [{phone}] Нажимаю '{text}'...")
                            await msg.click(btn=btn)
                            clicked = True
                            break
                if clicked:
                    break

        await asyncio.sleep(3)

        # Проверить ответ
        msgs2 = await client.get_messages(bot, limit=3)
        for m in msgs2:
            if m.text and ('добро' in m.text.lower() or 'welcome' in m.text.lower() or 'реферал засчитан' in m.text.lower()):
                print(f"  🎉 [{phone}] Реферал засчитан!")
                return True
            elif m.text:
                print(f"  ℹ️  [{phone}] Ответ бота: {m.text[:100]!r}")

        return clicked  # если кнопку нажали, считаем успехом

    except Exception as e:
        import traceback
        print(f"  ❌ [{phone}] Ошибка: {e}")
        traceback.print_exc()
        return False
    finally:
        await client.disconnect()


async def main():
    print("\n" + "═"*60)
    print("  RefAgent Referral Blast Test")
    print("  Проводник uid:", CONDUCTOR_UID)
    print("  Цель:         @" + TARGET_BOT)
    print("  Аккаунтов:   ", len(REFAGENT_ACCOUNTS))
    print("═"*60)

    before = db_ref_count(CONDUCTOR_UID)
    print(f"\nРефералов до теста: {before}")

    results = []
    for i, (phone, session) in enumerate(REFAGENT_ACCOUNTS):
        if i > 0:
            print(f"\n  ⏱  Пауза {WAIT_BETWEEN}s перед следующим аккаунтом...")
            await asyncio.sleep(WAIT_BETWEEN)
        ok = await do_referral(phone, session)
        results.append((phone, ok))

    after = db_ref_count(CONDUCTOR_UID)

    print("\n" + "═"*60)
    print("  РЕЗУЛЬТАТЫ")
    print("═"*60)
    for phone, ok in results:
        mark = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {mark}  {phone}")
    print(f"\nРефералов до:  {before}")
    print(f"Рефералов после: {after}")
    delta = after - max(before, 0)
    print(f"Новых рефералов: {delta}/{len(REFAGENT_ACCOUNTS)}")

    if delta >= len(REFAGENT_ACCOUNTS):
        print(f"\n🎉 BLAST TEST: PASS — все {delta} реферала засчитаны!")
    elif delta > 0:
        print(f"\n⚠️  BLAST TEST: PARTIAL — {delta}/{len(REFAGENT_ACCOUNTS)}")
    else:
        print(f"\n❌ BLAST TEST: FAIL — 0 рефералов засчитано")


if __name__ == "__main__":
    asyncio.run(main())
