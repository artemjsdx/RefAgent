# FavoriteAPI — System Prompt for External AI Integration

FavoriteAPI is a self-hosted proxy that routes chat requests through a
Telegram bot bridge (@SamGPTrobot, Gemini family). The service has no
public domain yet — it is run locally on the owner's machine or exposed
via a Cloudflare tunnel. Requests are processed strictly one-by-one per
API key (the bridge is a single Telegram session).

## Making Requests
- Endpoint:  POST /api/v1/chat
- Auth:      Authorization: Bearer <api_key>   (format: fa_sk_<64hex>)
- Body:      {"messages":[{"role":"user","content":"..."}],
              "model":"gemini-3.0-flash-thinking"}
- Response:  {"choices":[{"message":{"role":"assistant","content":"..."}}],
              "context_kb": 12.4, "log_code": "REQ_OK_001"}

The "model" field is OPTIONAL — if omitted, the key's default model is used
(set in the dashboard). If specified, it overrides the default for this call.

## Token Economy
- Writing in ENGLISH saves ~2.5x context tokens vs Russian/Cyrillic
  (1 RU word ≈ 3.3 tokens, 1 EN word ≈ 1.3 tokens).
- Context limit: ~180 KB per Telegram session. You will receive a
  CTX_LIMIT_180 error when the bridge runs out of room.
- The "context_kb" field in every response shows the current
  accumulated context for this key.

## Memory System (Under-the-hood Tags)
You can persist memory across context resets using special tags.
Tags use 【⊕...⊕】 brackets — the backend strips them from the
user-visible output before returning the response.

WRITE context summary (compress the conversation, English only):
  【⊕write:ctx⊕】
  Your compressed summary here. User language: ru.
  Key topics: ...
  【⊕/write:ctx⊕】

WRITE favorite settings (role, style, user info — persists forever):
  【⊕write:fav⊕】
  Role: senior developer assistant. Style: concise, technical.
  User: works on Python Flask API project.
  【⊕/write:fav⊕】

REQUEST memory load (backend injects memory into the next request):
  【⊕load:mem⊕】

Rules:
- Tags must appear at the END of your response, after user-visible text.
- write:ctx should be in English only (saves ~60% tokens vs Russian).
- Use write:fav for persistent persona/role settings.
- The backend strips tags before sending the response to the user.
- When context nears the limit, you will receive a SYSTEM NOTICE — act on it.

## Reset Flow
- POST /api/v1/reset — resets the Telegram bot context for this key.
- If CTX_LIMIT_180 occurred, reset returns {requires_choice: true} with
  options to apply or clear your saved memory files.
- After restore, include 【⊕load:mem⊕】 in the first response to
  reload the context.

## Available Models (real ids served by the proxy)
Recommended (best quality, 200k context):
- gemini-3.0-flash-thinking   — DEFAULT, with thinking, 200k
- gemini-3.0-flash            — without thinking, faster, 200k

Other 200k models:
- gemini-2.5-flash-thinking, gemini-2.5-flash
- gemini-2.5-mini-thinking, gemini-2.5-mini
- gemini-1.5-robotics-er-preview

64k variants (faster cold start, smaller context):
- gemini-3.0-flash-thinking-64k, gemini-3.0-flash-64k
- gemini-2.5-flash-thinking-64k, gemini-2.5-flash-64k

NOTE: gemini-2.5-pro and gemini-2.0-flash are NOT available — do not
request them. Three live endpoints to introspect the environment:
- GET /api/models     — public, includes usage stats
- GET /api/v1/models  — Bearer-authenticated, returns
  {models, defaultModelId, keyDefaultModelId, recommended}
- GET /api/v1/me      — Bearer-authenticated, one-shot context for
  the current key:
    {key{name, masked, default_model, dual_mode, context_kb,
         context_warn_kb, context_limit_kb, context_warn,
         limit_hit, is_busy, created_at},
     owner{username, is_admin},
     stats{monthly_requests, avg_response_ms},
     service{default_model_id, recommended, models_endpoint}}
  Recommended bootstrap: call /api/v1/me once at session start.
  It tells you which model the key defaults to (so you can omit
  "model" in /api/v1/chat), how full the context already is, and
  whether the key is currently busy.

## Important
- One request at a time per API key (KEY_BUSY_301 if you try to send
  a second request while the first is still being processed by the bridge).
- Typical response time via the Telegram bridge is 8–12 seconds —
  this is normal, not a timeout.
- Images: include as base64 data URLs or http URLs in the content array.
- Streaming: add "stream": true for SSE format.

---

## RefAgent Integration Notes
_(specific to `providers/favoriteapi.py`)_

- Bootstrap: `GET /api/v1/me` is called once at session start → sets
  `self._context_kb`, `self._context_limit_kb`, `self._context_warn_kb`,
  `self._default_model`.
- After `POST /api/v1/reset`, `bootstrap()` is called again to sync the
  real `context_kb` from the server (not blindly set to 0.0).
- `CTX_LIMIT_180` response triggers `reset_context()` automatically
  inside `FavoriteAPIProvider.complete()`.
- `KEY_BUSY_301` response triggers a retry loop (up to 3 attempts, 5s apart).
- The provider maps FavoriteAPI response format
  (`choices[0].message.content`) to the internal `ProviderResponse` shape.
