"""Тесты REST API (AT-01 ... AT-10). Очередь Redis подменяется заглушкой."""
import json

import pytest
import redis
from fastapi.testclient import TestClient

QUEUE_KEY = "ticket_assignment"


class FakeQueue:
    """Минимальная замена redis.Redis для тестов API."""

    def __init__(self):
        self.items = {}
        self.fail = False

    def ping(self):
        if self.fail:
            raise redis.RedisError("queue is down")
        return True

    def zadd(self, name, mapping):
        if self.fail:
            raise redis.RedisError("queue is down")
        self.items.setdefault(name, {}).update(mapping)


@pytest.fixture()
def client(monkeypatch):
    from app import models  # noqa: F401
    from app.db import Base, engine
    from app import main

    Base.metadata.drop_all(bind=engine)
    fake = FakeQueue()
    monkeypatch.setattr(main, "queue", fake)
    with TestClient(main.app) as test_client:  # запускает lifespan: таблицы и специалисты
        test_client.fake = fake
        yield test_client


def create(client, **overrides):
    payload = {"title": "Не работает VPN", "description": "Нет подключения",
               "category": "network", "priority": 3}
    payload.update(overrides)
    return client.post("/api/tickets", json=payload)


def test_at01_create_normalizes_and_queues(client):
    response = create(client, title="  Проблема с VPN  ", category="  Network ")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "queued"
    assert data["category"] == "network"
    assert data["title"] == "Проблема с VPN"


def test_at02_queue_score_formula(client):
    data = create(client, priority=2).json()
    members = client.fake.items[QUEUE_KEY]
    key = json.dumps({"ticket_id": data["id"]})
    assert members[key] == 2 * 1_000_000_000 + data["id"]


def test_at03_priority_order_in_queue(client):
    ids = [create(client, priority=p).json()["id"] for p in (5, 3, 1)]
    ordered = sorted(client.fake.items[QUEUE_KEY].items(), key=lambda kv: kv[1])
    popped = [json.loads(member)["ticket_id"] for member, _score in ordered]
    assert popped == [ids[2], ids[1], ids[0]]


@pytest.mark.parametrize("overrides", [
    {"title": "ab"},
    {"priority": 6},
    {"priority": 0},
    {"description": "x"},
])
def test_at04_validation_errors(client, overrides):
    assert create(client, **overrides).status_code == 422


def test_at05_queue_failure_returns_503_and_keeps_ticket_new(client):
    client.fake.fail = True
    response = create(client)
    assert response.status_code == 503
    tickets = client.get("/api/tickets").json()
    assert len(tickets) == 1
    assert tickets[0]["status"] == "new"


def test_at06_in_progress_requires_agent(client):
    ticket_id = create(client).json()["id"]
    response = client.patch(f"/api/tickets/{ticket_id}/status", params={"status": "in_progress"})
    assert response.status_code == 409


def test_at07_status_change_after_assignment(client):
    from app.assignment import assign_ticket
    from app.db import SessionLocal

    ticket_id = create(client, category="network").json()["id"]
    with SessionLocal() as session:
        assign_ticket(session, ticket_id)
    response = client.patch(f"/api/tickets/{ticket_id}/status", params={"status": "in_progress"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["agent_name"] is not None


def test_at08_invalid_status_and_unknown_ticket(client):
    ticket_id = create(client).json()["id"]
    assert client.patch(f"/api/tickets/{ticket_id}/status", params={"status": "done"}).status_code == 422
    assert client.patch("/api/tickets/99999/status", params={"status": "closed"}).status_code == 404


def test_at09_seed_agents_present(client):
    names = [a["name"] for a in client.get("/api/agents").json()]
    assert names == ["Анна Смирнова", "Иван Петров", "Мария Волкова"]


def test_at10_health_ok_and_degraded(client):
    ok = client.get("/health")
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"
    client.fake.fail = True
    degraded = client.get("/health")
    assert degraded.status_code == 503
    assert degraded.json()["status"] == "degraded"
