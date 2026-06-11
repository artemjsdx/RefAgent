# RefAgent — Knowledge Base

> Lessons learned from real referral testing (6+ successful referrals, dozens of errors).
> Source: testing @chatplusddfbot, June 2026.

---

## Account Restrictions by UID

| UID Range | Can DM bot | Can resolve username | Can join channel | Can create group |
|-----------|-----------|---------------------|-----------------|-----------------|
| > 8,500,000,000 (FRESH) | ❌ | ❌ | ⚠️ sometimes | ❌ |
| 8,000,000,000 – 8,500,000,000 | ❌ | ⚠️ | ⚠️ | ❌ |
| 7,600,000,000 – 8,000,000,000 | ❌ | ✅ mostly | ✅ mostly | ❌ |
| < 7,600,000,000 | ❌ | ✅ | ✅ | ⚠️ depends on warmup |
| Warmed (CONDUCTOR) | ✅ | ✅ | ✅ | ✅ |

**Key insight:** 0/8 tested accounts could DM bot directly. Conductor always required.

---

## Error Reference

### RandomIdEmptyError
- **Cause:** `random_id=0` in SendMessageRequest
- **Fix:** `int.from_bytes(os.urandom(8), 'big', signed=True)`

### PeerIdInvalidError (DM to bot)
- **Cause:** Fresh/limited account cannot DM unknown bot
- **Fix:** Use Harold conductor pattern (create group, join via invite)
- **NOT fixed by:** different api_id, delays, parameters

### ValueError: Could not find input entity for PeerUser
- **Cause:** `get_entity(chat_id)` returned PeerUser instead of PeerChat
- **Fix:** Use `InputPeerChat(chat_id)` directly, skip get_entity

### InviteHashExpiredError
- **Cause 1:** Wrong regex — `\w+` misses `-` and `_` in hash
- **Cause 2:** Fresh account was already added to group by conductor
- **Fix 1:** Use `/(?:joinchat/|\+)([A-Za-z0-9_-]+)/` regex
- **Fix 2:** Create group with BOT ONLY, fresh joins separately via invite

### ChannelInvalidError (JoinChannelRequest)
- **Cause:** Wrong or zero access_hash. access_hash is session-specific.
- **Fix:** `entity = await client.get_entity("username")` then `JoinChannelRequest(channel=entity)`

### ChatAdminRequiredError (ExportChatInviteRequest)
- **Cause:** Trying to export invite from a channel where you're not admin
- **Fix:** Only export invites from groups YOU created. For public channels use get_entity + JoinChannel.

### AttributeError on session connect
- **Cause:** Session file is TDesktop or Pyrogram format, not Telethon SQLite
- **Fix:** Check first bytes (`SQLite format 3\x00` = SQLite). TDesktop has different table structure.

### KEY_BUSY_301 (FavoriteAPI)
- **Cause:** Sending second request before first finished
- **Fix:** Ensure sequential requests, use asyncio lock per api_key

### CTX_LIMIT_180 (FavoriteAPI)
- **Cause:** 180KB context limit hit
- **Fix:** POST /api/v1/reset → on restore include `【⊕load:mem⊕】` in first message

---

## Bot Detection: Group vs DM-only

- **Test:** Send `/start` to group, wait 7 seconds, check iter_messages
- **Group-capable:** Bot responds in group → referral works via group
- **DM-only:** No response in group → referral MAY still work (some bots credit /start regardless)
- **No API to detect this** — must test empirically
- **Bot Privacy Mode:** If enabled in @BotFather, bot won't see group messages at all

---

## Referral Crediting Logic (@chatplusddfbot specific)

- Referral credited at `/start inv_CODE` — DM not required if bot accepts groups
- UID > 8,500,000,000 → NOT credited (bot-side check)
- Max 10 referrals per day (resets at UTC+8 midnight)
- 60 second minimum between credits
- Sending too fast → silently not credited (no error)

---

## Session File Formats

| Format | Detection | Connection |
|--------|-----------|------------|
| Telethon | SQLite, tables: sessions + entities | `TelegramClient(path, api_id, api_hash)` |
| TDesktop | SQLite, different tables | Convert with tg-sec or use TData |
| Zip+JSON sidecar | `.session` + `.json` with app_id/app_hash | Use JSON credentials |

**CRITICAL:** Always use `api_id` and `api_hash` from the sidecar JSON, not global credentials.
One shared api_id across accounts = mass freeze.

---

## Warmup Factors (what makes an account a conductor)

| Factor | Minimum |
|--------|---------|
| Account age | > 1-2 weeks |
| Number of chats | > 10-15 |
| Contacts | > 5 |
| Activity | Sent messages, read channels |
| 2FA | Enabled (strong signal) |
| Avatar | Set |

**Programmatic warmup:** Join 3-5 public groups, send messages, set avatar, add contacts.
No guaranteed timeline — usually 3-7 days of light activity.
