# PeerIdInvalidError (DM к боту)

**Ошибка:** `PeerIdInvalidError` при попытке написать боту напрямую

## Причина
Аккаунт не может отправить DM неизвестному боту. Протестировано на 8/8 аккаунтах — ни один не смог. Не зависит от UID, api_id, задержек или параметров.

## Решение
Использовать паттерн Harold Conductor:
1. Проводник создаёт группу с ботом: `CreateChatRequest(users=[InputUser(BOT_ID, BOT_HASH)])`
2. Проводник экспортирует инвайт: `ExportChatInviteRequest`
3. Извлечь хэш: `/(?:joinchat/|\+)([A-Za-z0-9_-]+)/` (важно: `-` и `_` в классе символов!)
4. Свежий аккаунт вступает: `ImportChatInviteRequest(hash=extracted_hash)`
5. Свежий пишет в группу: `SendMessageRequest(peer=InputPeerChat(chat_id), ...)`

## НЕ помогает
- Смена api_id/api_hash
- Задержки перед отправкой
- Другие параметры запроса
- ResolveUsernameRequest перед DM

## Источник
Тестирование @chatplusddfbot, июнь 2026. 6+ успешных рефералов через conductor pattern.
