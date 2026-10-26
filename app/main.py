import json
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
import redis
from .db import Base, engine, get_db, SessionLocal
from .models import Agent, Ticket
from .schemas import TicketCreate, TicketOut, AgentOut

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
queue = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def init_database():
    for attempt in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as db:
                if db.scalar(select(Agent.id).limit(1)) is None:
                    db.add_all([
                        Agent(name="Анна Смирнова", skills="network,hardware,general"),
                        Agent(name="Иван Петров", skills="software,access,general"),
                        Agent(name="Мария Волкова", skills="software,network,general"),
                    ])
                    db.commit()
            return
        except Exception:
            if attempt == 29:
                raise
            time.sleep(2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(title="Support Dispatcher API", version="1.0.0", lifespan=lifespan)

def ticket_to_out(ticket: Ticket) -> TicketOut:
    return TicketOut(id=ticket.id, title=ticket.title, description=ticket.description,
        category=ticket.category, priority=ticket.priority, status=ticket.status,
        agent_id=ticket.agent_id, agent_name=ticket.agent.name if ticket.agent else None,
        created_at=ticket.created_at, assigned_at=ticket.assigned_at)

@app.get("/health")
def health():
    try:
        queue.ping()
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"status": "ok", "database": "ok", "queue": "ok"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "detail": str(exc)})

@app.get("/api/agents", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.scalars(select(Agent).order_by(Agent.id)).all()

@app.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(db: Session = Depends(get_db)):
    tickets = db.scalars(select(Ticket).order_by(Ticket.created_at.desc())).all()
    return [ticket_to_out(t) for t in tickets]

@app.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(title=payload.title.strip(), description=payload.description.strip(),
                    category=payload.category.strip().lower(), priority=payload.priority, status="queued")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    try:
        queue.zadd("ticket_assignment", {json.dumps({"ticket_id": ticket.id}): payload.priority * 1_000_000_000 + ticket.id})
    except redis.RedisError as exc:
        ticket.status = "new"
        db.commit()
        raise HTTPException(status_code=503, detail="Очередь временно недоступна; заявка сохранена как новая") from exc
    return ticket_to_out(ticket)

@app.patch("/api/tickets/{ticket_id}/status", response_model=TicketOut)
def update_status(ticket_id: int, status: str, db: Session = Depends(get_db)):
    allowed = {"in_progress", "resolved", "closed"}
    if status not in allowed:
        raise HTTPException(status_code=422, detail=f"Допустимые статусы: {', '.join(sorted(allowed))}")
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if status == "in_progress" and ticket.agent_id is None:
        raise HTTPException(status_code=409, detail="Нельзя начать необработанную заявку без исполнителя")
    ticket.status = status
    db.commit()
    db.refresh(ticket)
    return ticket_to_out(ticket)
