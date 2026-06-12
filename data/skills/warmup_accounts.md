---
  name: warmup_accounts
  title: Прогрев новых аккаунтов
  type: workflow
  tags: ["warmup", "fresh", "accounts", "preparation", "new"]
  scope: global
  active: true
  created: 2026-06-12
  ---

  ## Описание
  Шаблон плана для прогрева свежих (FRESH) аккаунтов перед основными задачами. Снижает риск бана.

  ## Шаги
  1. list_accounts → отфильтровать ACTIVE аккаунты с категорией FRESH
  2. Для каждого аккаунта: connect_account → проверить статус и uid_category
  3. join_channel для 2-3 публичных каналов по теме (новости, крипта, технологии)
  4. sleep_seconds(300) — пауза 5 минут между каждым аккаунтом
  5. Отчёт: сколько аккаунтов прогрето, какие статусы
  