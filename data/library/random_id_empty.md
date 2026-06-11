# RandomIdEmptyError

**Ошибка:** `RandomIdEmptyError` при `SendMessageRequest`

## Причина
Передан `random_id=0`. Telegram отвергает нулевые random_id.

## Решение
```python
import os
random_id = int.from_bytes(os.urandom(8), 'big', signed=True)
# random_id гарантированно ненулевой и уникальный
```

## Никогда не использовать
```python
random_id = 0          # ошибка
random_id = 1          # коллизии между запросами
random_id = random.randint(0, 999)  # слишком мало пространство, коллизии
```

## Применяется везде
Любой `SendMessageRequest`, `ForwardMessagesRequest` и другие MTProto запросы с полем `random_id`.
