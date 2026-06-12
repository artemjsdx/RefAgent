# Telegram Mechanics — общие правила работы с аккаунтами

## Категории UID и возможности

| Категория | UID Range           | Возможности |
|-----------|---------------------|-------------|
| OLD       | < 7 000 000 000     | Максимум прав |
| NORMAL    | 7B – 8.5B           | Можно resolve username, join channels, DM заблокированы |
| FRESH     | > 8 500 000 000     | Только ImportChatInviteRequest надёжен |
| CONDUCTOR | любой (прогретый)   | CreateChat, ResolveUsername, экспорт invite |

## Harold Conductor — обязателен на 100%
100% аккаунтов (даже OLD) не могут писать ботам в личку без истории.
Conductor создаёт группу → добавляет бота → аккаунты вступают через invite.

## API credentials
- Каждый аккаунт = свой api_id/api_hash из .json сайдкара
- Никогда не шарить api_id между аккаунтами
- Безопасный fingerprint: api_id=2040, system_version="4.16.30-vxCUSTOM" (Telegram Desktop)

## Сессионные файлы
- Формат: `+PHONE.session` + `+PHONE.json` сайдкар
- Дубликаты `+PHONE (1).session` → пропускать
- Числовые `239913XXX_telethon` → нет привязки к телефону, статус неизвестен

## Таймаут между действиями (антибан)
- Между StartBotRequest для разных ботов: 4с минимум
- После вступления в канал: 35с
- Между аккаунтами при последовательной обработке: 20–30с
- Между засчитанными рефералами: 60с минимум

## random_id
ВСЕГДА: `int.from_bytes(os.urandom(8), 'big', signed=True)`
Никогда не использовать 0 — вызывает ошибку Telegram.

## Кнопки в ботах
- **Subscribe/Join/Channel URL-кнопки** → KeyboardButtonUrl → `get_inline_button_urls` → `join_channel`
  НЕ нажимать через click_button — они не отправляют callback!
- **Verify/Проверить callback-кнопки** → `click_button` (отправляет data)
