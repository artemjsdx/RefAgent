# Общий паттерн реферальной накрутки

## Разведка нового бота (learn_pattern)

1. **Открыть бота** с реф-параметром: `start_bot(account_id, bot, param)`
2. **Читать сообщения**: `get_messages` — смотреть что требует бот
3. **Если есть URL-кнопки** (каналы для подписки):
   - `get_inline_button_urls` → берём url_buttons
   - Для каждого URL: `join_channel(account_id, url)`
4. **Если есть callback-кнопки** (Проверить/Verify):
   - `click_button(account_id, bot, message_id, button_text="Проверить")`
5. **Verify**: снова `get_messages` — ищем признак успеха

## Порядок каналов (критично для FloodWait)

Telegram считает `ImportChatInviteRequest` в скользящем окне ~5 минут.
- Самый важный (основной) канал — ВСЕГДА ПЕРВЫМ (до остальных invite-ссылок)
- Он занимает слот 1 пока окно свободно → вступает мгновенно
- Последний в очереди получает FloodWait → retry → success

## Типы условий рефбота

| Условие       | Как выполнять                              |
|---------------|---------------------------------------------|
| Вступить в канал (invite-ссылка) | `join_channel(url)` с FloodWait retry |
| Вступить в канал (открытый)      | `join_channel(@username)` через JoinChannelRequest |
| Запустить спонсор-бота           | `start_bot(bot, param)` — 4с между каждым |
| Approval-канал                   | `join_channel` → `InviteRequestSentError` = УСПЕХ |
| Проверить подписку               | `click_button` с callback data |

## Признаки успешного реферала
- Бот отвечает приветственным сообщением (не суб-экраном)
- Ключевые фразы: "добро пожаловать", "бонус", "реферал засчитан", "ежедневный"
- Отсутствие кнопок "Подписаться" в последнем сообщении

## Параллельный запуск (ВСЕГДА)

```python
n = len(sessions)          # CONCURRENCY = все аккаунты сразу
sem = asyncio.Semaphore(n)
tasks = [process_one(phone, path, sem) for phone, path in sessions]
await asyncio.gather(*tasks, return_exceptions=True)
```

Никогда не зашивать CONCURRENCY = 3.
Пользователь говорит "все аки" → concurrency = len(accounts).

## Время на аккаунт (типично)
~6–8 минут из-за FloodWait на approval-каналах.
При параллельном запуске: все финишируют одновременно через ~7 мин.
