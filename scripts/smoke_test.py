#!/usr/bin/env python3
"""Дымовой тест развёрнутой системы (только стандартная библиотека Python).

Проверяет /health, создаёт заявку и ждёт, пока фоновый обработчик назначит исполнителя.
Использование: python smoke_test.py [BASE_URL]   (по умолчанию http://localhost:8080)
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")


def request(path, data=None, timeout=5):
    req = urllib.request.Request(BASE + path, method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


print(f"[1/3] Проверка {BASE}/health")
for attempt in range(1, 41):
    try:
        status, body = request("/health")
        print(f"  попытка {attempt}: HTTP {status} {body}")
        if status == 200:
            break
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  попытка {attempt}: {exc}")
    if attempt == 40:
        print("Сервис не ответил на /health за 40 попыток", file=sys.stderr)
        sys.exit(1)
    time.sleep(3)

print("[2/3] Создание тестовой заявки")
_, ticket = request("/api/tickets", {"title": "Smoke test", "description": "Automatic smoke test",
                                      "category": "network", "priority": 1})
print(f"Создана заявка №{ticket['id']}")

print("[3/3] Ожидание назначения исполнителя")
for attempt in range(1, 21):
    _, tickets = request("/api/tickets")
    current = next((t for t in tickets if t["id"] == ticket["id"]), None)
    state = current["status"] if current else "не найдена"
    print(f"  попытка {attempt}: статус {state}")
    if state == "assigned":
        print("Smoke-тест пройден")
        sys.exit(0)
    time.sleep(1)

print("Заявка не была назначена вовремя", file=sys.stderr)
sys.exit(1)
