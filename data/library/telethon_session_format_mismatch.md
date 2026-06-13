# Telethon: too many values to unpack (expected 5)

**Ошибка:** `ValueError: too many values to unpack (expected 5)` в `telethon/sessions/sqlite.py:64`

## Причина
Файл `.session` был создан в другой версии Telethon или с другой структурой таблицы `sessions`. Структура таблицы изменилась между версиями.

## Решение

### Способ 1: Пересоздать сессию (рекомендуется)
```bash
python -m telethon.sessions.session_name
```

### Способ 2: Конвертировать сессию
Если есть исходный `.session` файл от другого формата, используй конвертер:

```python
from telethon.sessions import SQLiteSession

# Открыть старую сессию и сохранить в новом формате
old_session = SQLiteSession('old.session')
# ...работа с клиентом...
```

### Способ 3: Удалить и пересоздать
Если аккаунт доступен по телефону — проще удалить `.session` и авторизоваться заново.

## Проверка структуры сессии
```python
import sqlite3
conn = sqlite3.connect('file.session')
cursor = conn.execute("PRAGMA table_info(sessions)")
for row in cursor:
    print(row)
```

## Примечание
Сессии от Pyrogram, Telethon разных версий, или сессии с кастомными полями — несовместимы. Каждый api_id должен иметь свою уникальную сессию.