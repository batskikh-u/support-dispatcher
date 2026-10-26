from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Agent, Ticket, utcnow

ACTIVE_STATUSES = ("assigned", "in_progress")

def choose_agent(db: Session, category: str) -> Agent | None:
    """Выбирает активного специалиста с минимальной нагрузкой.

    Сначала рассматриваются сотрудники, у которых category указана в skills
    (список через запятую); если таких нет, используется любой активный специалист.
    При равной нагрузке выбирается сотрудник с меньшим id.
    """
    agents = db.scalars(select(Agent).where(Agent.is_active.is_(True)).order_by(Agent.id)).all()
    if not agents:
        return None
    specialized = [a for a in agents if category.lower() in [s.strip().lower() for s in a.skills.split(",")]]
    candidates = specialized or agents
    loads = dict(db.query(Ticket.agent_id, func.count(Ticket.id))
                 .filter(Ticket.agent_id.is_not(None), Ticket.status.in_(ACTIVE_STATUSES))
                 .group_by(Ticket.agent_id).all())
    return min(candidates, key=lambda a: (loads.get(a.id, 0), a.id))

def assign_ticket(db: Session, ticket_id: int) -> Ticket | None:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.status not in ("new", "queued"):
        return ticket
    agent = choose_agent(db, ticket.category)
    if agent is None:
        ticket.status = "unassigned"
    else:
        ticket.agent_id = agent.id
        ticket.status = "assigned"
        ticket.assigned_at = utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket
