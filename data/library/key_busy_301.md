# KEY_BUSY_301 (FavoriteAPI)

**Ошибка:** `log_code: "KEY_BUSY_301"` в ответе FavoriteAPI

## Причина
Отправлен второй запрос пока первый ещё обрабатывается. FavoriteAPI допускает только один запрос за раз на ключ.

## Решение
В `providers/favoriteapi.py` уже реализован `asyncio.Lock()`:
```python
async with self._lock:
    return await self._do_chat(messages, tools, model)
```

Если ошибка всё равно появляется — проверь что используется один экземпляр `FavoriteAPIProvider` (не создаётся новый на каждый запрос).

## Повторная попытка
При получении KEY_BUSY_301 — подождать 3-5 секунд и повторить. Это временное состояние.

## Источник
Документация FavoriteAPI, тестирование июнь 2026.
