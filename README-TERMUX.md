# RefAgent в Termux

## Установка

```bash
pkg update && pkg install python git
git clone https://github.com/artemjsdx/RefAgent
cd RefAgent
pip install -r requirements.txt
```

## Настройка

```bash
cp .env.example .env
nano .env       # вставь API ключи
```

Создай `config/config.json` с токеном бота:
```json
{"bot_token": "ТУТ_ТОКЕН_ОТ_BOTFATHER", "active_provider": "openrouter"}
```

## Запуск

```bash
bash run.sh
# или напрямую:
python3 refagent.py
```

## Сессии аккаунтов

Положи `.session` файлы в `data/sessions/`.
Каждому `.session` должен лежать рядом `.json` sidecar с `app_id` и `app_hash`.

## Провайдеры LLM

| Провайдер | Модель | Статус |
|-----------|--------|--------|
| OpenRouter | openai/gpt-oss-20b:free | ✅ Free |
| b.ai | kimi-k2.5 | ✅ Free (500K tokens) |
| FavoriteAPI | gemini-3.0-flash-thinking | ✅ Self-hosted Gemini |

## Тесты

```bash
python3 tests/test_providers.py          # все провайдеры
python3 tests/test_providers.py openrouter bai
python3 tests/test_referral_blast.py     # реальная накрутка
```
