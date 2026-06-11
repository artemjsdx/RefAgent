# ChatAdminRequiredError

**Ошибка:** `ChatAdminRequiredError` при `ExportChatInviteRequest`

## Причина
Попытка экспортировать инвайт из канала или группы где аккаунт не является администратором.

## Решение
Экспортировать инвайт можно только из группы которую ты сам создал:
```python
# 1. Проводник создаёт группу
result = await conductor_client(CreateChatRequest(
    users=[InputUser(BOT_ID, BOT_HASH)],
    title="Temp"
))
chat_id = result.chats[0].id

# 2. Экспортируем инвайт из СВОЕЙ группы
invite = await conductor_client(ExportChatInviteRequest(
    peer=InputPeerChat(chat_id)
))
```

## Нельзя делать
```python
# Нельзя экспортировать инвайт из публичного канала
invite = await client(ExportChatInviteRequest(peer="@public_channel"))  # ChatAdminRequiredError
```

## Для публичных каналов
Использовать `get_entity` + `JoinChannelRequest` — инвайт не нужен.
