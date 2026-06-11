# InviteHashExpiredError

**Ошибка:** `InviteHashExpiredError` при `ImportChatInviteRequest`

## Причина 1 — Неправильный regex для извлечения хэша
Regex `\w+` не захватывает символы `-` и `_`, которые встречаются в хэшах.

**Неправильно:**
```python
re.search(r'joinchat/(\w+)', link)
```

**Правильно:**
```python
re.search(r'(?:joinchat/|\+)([A-Za-z0-9_-]+)', link)
```

## Причина 2 — Свежий аккаунт уже добавлен в группу при создании
Если передать fresh аккаунт в `CreateChatRequest`, он автоматически становится участником.
Попытка вступить по инвайту провалится — он уже внутри.

**Неправильно:**
```python
CreateChatRequest(users=[InputUser(BOT_ID, BOT_HASH), InputUser(FRESH_ID, FRESH_HASH)])
```

**Правильно:**
```python
# Создаём группу ТОЛЬКО с ботом
CreateChatRequest(users=[InputUser(BOT_ID, BOT_HASH)])
# Свежий аккаунт вступает отдельно через инвайт
ImportChatInviteRequest(hash=extracted_hash)
```

## Источник
Тестирование @chatplusddfbot, июнь 2026.
