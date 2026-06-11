# Форматы Session-файлов

## Определение формата

```python
SQLITE_MAGIC = b"SQLite format 3\x00"

def detect_format(path):
    with open(path, 'rb') as f:
        header = f.read(16)
    if not header.startswith(SQLITE_MAGIC):
        return 'UNKNOWN'
    
    conn   = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    
    if 'sessions' in tables and 'entities' in tables:
        return 'TELETHON'
    return 'TDESKTOP'
```

## Telethon
- Формат: SQLite с таблицами `sessions` и `entities`
- Подключение: `TelegramClient(path, api_id, api_hash)`
- UID: читается из `SELECT user_id FROM sessions LIMIT 1`
- Sidecar JSON: **ОБЯЗАТЕЛЕН** — содержит `app_id` и `app_hash`

## TDesktop (не поддерживается)
- Формат: SQLite с другой структурой таблиц
- Требует конвертации (tg-sec или другие инструменты)
- RefAgent не поддерживает TDesktop нативно

## ZIP-архив
- Структура: `.session` + `.json` рядом в архиве
- JSON ключи: `app_id` (int), `app_hash` (str)
- RefAgent распаковывает в `data/sessions/<archive_name>/`

## КРИТИЧНО: Sidecar JSON
Каждый `.session` файл ДОЛЖЕН иметь рядом `.json` файл с:
```json
{
  "app_id": 12345678,
  "app_hash": "abcdef1234567890abcdef1234567890"
}
```

Использование одного api_id для нескольких аккаунтов = **массовая заморозка**.
