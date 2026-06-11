#!/usr/bin/env bash
# RefAgent — скрипт запуска для Termux/Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Проверить .env
if [ ! -f .env ]; then
  echo "⚠️  Нет .env — скопируй .env.example и заполни ключи"
  echo "    cp .env.example .env && nano .env"
  exit 1
fi

# Загрузить переменные
set -a; source .env; set +a

# Запустить
echo "▶ Запуск RefAgent..."
python3 refagent.py
