import json
import os
import time
import redis
from sqlalchemy import select
from .db import Base, engine, SessionLocal
from .models import Ticket
from .assignment import assign_ticket

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

def wait_for_database():
    for attempt in range(60):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("База данных не стала доступна за 120 секунд")

def main():
    wait_for_database()
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    while True:
        try:
            item = client.bzpopmin("ticket_assignment", timeout=5)
            if item is None:
                continue
            _, raw, _score = item
            message = json.loads(raw)
            with SessionLocal() as db:
                assign_ticket(db, int(message["ticket_id"]))
        except (redis.RedisError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"Ошибка обработки сообщения: {exc}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
