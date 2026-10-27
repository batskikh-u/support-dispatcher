#!/usr/bin/env bash
# Дымовой тест развёрнутой системы: проверяет /health, создаёт заявку
# и ждёт, пока фоновый обработчик назначит исполнителя.
# Использование: ./smoke_test.sh [BASE_URL]   (по умолчанию http://localhost:8080)
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"

echo "[1/3] Проверка ${BASE_URL}/health"
for attempt in $(seq 1 30); do
  if curl -fsS --max-time 3 "${BASE_URL}/health" > /dev/null; then
    break
  fi
  if [ "${attempt}" -eq 30 ]; then
    echo "Сервис не ответил на /health за 30 попыток" >&2
    exit 1
  fi
  sleep 2
done
curl -fsS "${BASE_URL}/health"; echo

echo "[2/3] Создание тестовой заявки"
RESPONSE=$(curl -fsS -X POST "${BASE_URL}/api/tickets" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Smoke test","description":"Automatic smoke test","category":"network","priority":1}')
TICKET_ID=$(echo "${RESPONSE}" | python3 -c 'import sys, json; print(json.load(sys.stdin)["id"])')
echo "Создана заявка №${TICKET_ID}"

echo "[3/3] Ожидание назначения исполнителя"
for attempt in $(seq 1 20); do
  STATUS=$(curl -fsS "${BASE_URL}/api/tickets" | python3 -c '
import json, sys
ticket_id = int(sys.argv[1])
for ticket in json.load(sys.stdin):
    if ticket["id"] == ticket_id:
        print(ticket["status"])
        break
' "${TICKET_ID}")
  echo "  попытка ${attempt}: статус ${STATUS}"
  if [ "${STATUS}" = "assigned" ]; then
    echo "Smoke-тест пройден"
    exit 0
  fi
  sleep 1
done

echo "Заявка не была назначена вовремя" >&2
exit 1
