# RefAgent — Architecture Deep Dive

## LLM Provider System

### OpenRouter
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Auth: `Authorization: Bearer $OPENROUTER_API_KEY`
- Model list: `GET https://openrouter.ai/api/v1/models` (cache 1 hour)
- Model browser: paginated 10/page, Free/Paid filter, manual input fallback
- Tool calling: standard OpenAI-compatible format

### FavoriteAPI
- Endpoint: `$FAVORITEAPI_URL/api/v1/chat`
- Auth: `Authorization: Bearer $FAVORITEAPI_KEY`
- Single request at a time per key (KEY_BUSY_301 if concurrent)
- Response includes `context_kb` — track this every call
- Context limit: 180KB per session
- Memory tags (stripped from output by backend):
  - `【⊕write:ctx⊕】...【⊕/write:ctx⊕】` — compress context (English only, saves 60%)
  - `【⊕write:fav⊕】...【⊕/write:fav⊕】` — persist role/settings forever
  - `【⊕load:mem⊕】` — reload memory after reset
- Auto-management: compress at >150KB, reset+restore at limit
- Bootstrap: call `GET /api/v1/me` at session start to get current context_kb

---

## ReAct Loop

```python
async def react_loop(user_message, stop_event):
    messages = [system_prompt] + history + [user_message]
    
    while not stop_event.is_set():
        response = await llm.chat(messages)
        
        if response.has_tool_calls:
            for call in response.tool_calls:
                # Show animated status block in Telegram
                await animator.start(chat_id, call.tool_name)
                
                # Execute tool
                result = await tools_registry.execute(call)
                
                # Replace status with permanent log
                await animator.finalize(chat_id, result.summary)
                
                messages.append(tool_result(call.id, result))
        else:
            # Final text response — loop ends
            await bot.send_message(chat_id, response.text, parse_mode="HTML")
            break
```

---

## Harold Conductor Pattern

**Problem:** 100% of accounts (even old UID < 8B) cannot send DMs to unknown bots.

**Solution:**
1. Conductor (warmed account) creates group: `CreateChatRequest(users=[InputUser(BOT_ID, BOT_HASH)])`
2. Conductor exports invite: `ExportChatInviteRequest(peer=InputPeerChat(chat_id))`
3. Extract hash with regex: `/(?:joinchat/|\+)([A-Za-z0-9_-]+)/` — **must include `-` and `_`**
4. Fresh account joins: `ImportChatInviteRequest(hash=extracted_hash)`
   - IMPORTANT: Do NOT add fresh to CreateChatRequest — only bot. Fresh joins via invite separately.
5. Fresh sends commands in group: `SendMessageRequest(peer=InputPeerChat(chat_id), ...)`
   - `random_id = int.from_bytes(os.urandom(8), 'big', signed=True)` — never 0!
6. After task: conductor deletes group (cleanup)

**Detecting bot group support:**
- Send `/start` to group, wait 7s, check iter_messages
- If response → ACCEPTS_GROUPS, cache in library/bot_@username.md
- If no response → DM_ONLY, warn user (referral may still work via /start in group)

**Inline buttons in group:**
- `GetBotCallbackAnswerRequest(peer=InputPeerChat(chat_id), msg_id=msg.id, data=button.data)`

---

## Session Format Detection

```python
def detect_format(path: str) -> str:
    with open(path, 'rb') as f:
        header = f.read(16)
    if header.startswith(b'SQLite format 3\x00'):
        # Check tables to distinguish Telethon vs TDesktop
        conn = sqlite3.connect(path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t[0] for t in tables}
        if 'sessions' in table_names and 'entities' in table_names:
            return 'TELETHON'
        return 'TDESKTOP'
    return 'UNKNOWN'
```

**Sidecar JSON** (zip sessions): read `app_id` and `app_hash` from `.json` file next to `.session`.
These MUST be used instead of global credentials.

---

## UID Categories

| Category | UID Range | Capabilities |
|----------|-----------|--------------|
| OLD | < 7,000,000,000 | Maximum rights (untested in project) |
| NORMAL | 7,000,000,000 – 8,500,000,000 | Can resolve usernames, join channels, DM blocked |
| FRESH | > 8,500,000,000 | Very limited — only ImportChatInviteRequest works reliably |
| CONDUCTOR | any (warmed) | Can CreateChat, ResolveUsername, export invites |

**Warmup indicators:** age > 1-2 weeks, 10+ chats, avatar set, 2FA enabled, contacts added.

---

## Bot Response Waiting

```python
async def wait_bot_response(client, peer, timeout=5, max_attempts=5):
    for attempt in range(max_attempts):
        await asyncio.sleep(timeout)
        messages = await client.get_messages(peer, limit=10)
        bot_messages = [m for m in messages if m.sender_id == BOT_ID]
        if bot_messages:
            return bot_messages[0]
        timeout = 2  # subsequent attempts shorter
    return None
```

**Timings:**
| Step | Wait | Reason |
|------|------|--------|
| After /start | 5s | Bot responds instantly |
| After /verify | 5s | Bot responds instantly |
| After button click | 3–5s | May have processing delay |
| Retry DM attempt | 10s | Pause between tries |
| Between referrals | 15–30s | 60s hard limit per credit |
| Between accounts | 15–20s | Avoid API spam |

---

## FavoriteAPI Memory Tags

Tags go at the END of agent response, stripped by backend before showing to user:

```
【⊕write:ctx⊕】
Conversation summary in English (saves ~60% tokens vs Russian).
User: working on RefAgent - Telegram referral automation.
Current task: implementing conductor pattern for fresh accounts.
【⊕/write:ctx⊕】
```

```
【⊕write:fav⊕】
Role: autonomous referral agent for Telegram.
Rules: always use unique api_id per account, always use conductor pattern,
always check knowledge library on errors, always build plan before starting work.
【⊕/write:fav⊕】
```

---

## Telegram Bot UI Patterns

### Animated status block
```python
# Send status, animate it, then replace with permanent log
msg = await bot.send_message(chat_id, "Working")
for frame in cycle(["Working", "Working.", "Working..", "Working..."]):
    await asyncio.sleep(0.8)
    await msg.edit_text(frame)
    if done: break
await msg.delete()
await bot.send_message(chat_id, f"✓ {log_text}", parse_mode="HTML")
```

### Plan display (HTML)
```html
<b>ПЛАН ЗАДАЧИ</b>

<b>Реф:</b> @botusername
<b>Код:</b> REF_CODE

<b>Шаги:</b>
1. Проверить UID
2. Join @channel
3. /start с кодом
4. /verify
5. Проверить начисление

<b>Аккаунтов:</b> 10
```

### Inline keyboard during task
```
[ Остановить ]  [ Стоп + написать ]
```
