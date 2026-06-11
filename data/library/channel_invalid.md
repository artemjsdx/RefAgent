# ChannelInvalidError

**Ошибка:** `ChannelInvalidError` при `JoinChannelRequest`

## Причина
Неправильный или нулевой `access_hash`. Access hash в Telegram специфичен для сессии — нельзя скопировать из другой сессии или захардкодить.

## Решение
```python
# Всегда получать entity через get_entity для текущей сессии
entity = await client.get_entity("@channel_username")
await client(JoinChannelRequest(channel=entity))
```

## Никогда не делать
```python
# Нельзя использовать access_hash из другой сессии
channel = InputChannel(channel_id=123456, access_hash=0)
await client(JoinChannelRequest(channel=channel))  # ChannelInvalidError
```

## Дополнительно
- `access_hash` обновляется при каждом подключении сессии
- Для каналов без username используй `InputChannel` с актуальным hash из `get_entity`
