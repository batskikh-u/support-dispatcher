"""Модульные тесты алгоритма распределения заявок (UT-01 ... UT-10)."""
from app.assignment import assign_ticket, choose_agent
from app.models import Agent, Ticket


def make_agent(db, name, skills, active=True):
    agent = Agent(name=name, skills=skills, is_active=active)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def make_ticket(db, category="general", status="queued", agent_id=None, priority=3):
    ticket = Ticket(title="Тестовая заявка", description="Описание", category=category,
                    priority=priority, status=status, agent_id=agent_id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def seed_three(db):
    anna = make_agent(db, "Анна Смирнова", "network,hardware,general")
    ivan = make_agent(db, "Иван Петров", "software,access,general")
    maria = make_agent(db, "Мария Волкова", "software,network,general")
    return anna, ivan, maria


def test_ut01_category_equal_load_picks_lowest_id(db):
    anna, _ivan, _maria = seed_three(db)
    assert choose_agent(db, "network").id == anna.id


def test_ut02_balancing_prefers_less_loaded(db):
    anna, _ivan, maria = seed_three(db)
    make_ticket(db, status="assigned", agent_id=anna.id)
    assert choose_agent(db, "network").id == maria.id


def test_ut03_no_specialist_falls_back_to_any_active(db):
    anna, ivan, maria = seed_three(db)
    make_ticket(db, status="assigned", agent_id=anna.id)
    make_ticket(db, status="in_progress", agent_id=anna.id)
    make_ticket(db, status="assigned", agent_id=ivan.id)
    make_ticket(db, status="assigned", agent_id=maria.id)
    # категории printing нет ни у кого: Иван и Мария имеют нагрузку 1, у Ивана меньше id
    assert choose_agent(db, "printing").id == ivan.id


def test_ut04_inactive_agent_is_excluded(db):
    anna, _ivan, maria = seed_three(db)
    anna.is_active = False
    db.commit()
    assert choose_agent(db, "network").id == maria.id


def test_ut05_no_active_agents_marks_unassigned(db):
    make_agent(db, "Неактивный", "network", active=False)
    ticket = make_ticket(db, category="network")
    result = assign_ticket(db, ticket.id)
    assert result.status == "unassigned"
    assert result.agent_id is None
    assert result.assigned_at is None


def test_ut06_finished_tickets_do_not_count_as_load(db):
    anna, _ivan, maria = seed_three(db)
    for _ in range(3):
        make_ticket(db, status="resolved", agent_id=anna.id)
    make_ticket(db, status="assigned", agent_id=maria.id)
    assert choose_agent(db, "network").id == anna.id


def test_ut07_assign_is_idempotent_for_processed_ticket(db):
    anna, _ivan, maria = seed_three(db)
    ticket = make_ticket(db, category="network", status="in_progress", agent_id=maria.id)
    result = assign_ticket(db, ticket.id)
    assert result.status == "in_progress"
    assert result.agent_id == maria.id


def test_ut08_skills_are_case_and_space_insensitive_and_beat_load(db):
    first = make_agent(db, "Специалист 1", " Network ,hardware")
    second = make_agent(db, "Специалист 2", "software")
    make_ticket(db, status="assigned", agent_id=first.id)
    # у первого нагрузка выше, но он единственный профильный
    assert choose_agent(db, "network").id == first.id
    assert second.id != first.id


def test_ut09_unknown_ticket_returns_none(db):
    seed_three(db)
    assert assign_ticket(db, 99999) is None


def test_ut10_status_new_is_assignable(db):
    anna, _ivan, _maria = seed_three(db)
    ticket = make_ticket(db, category="network", status="new")
    result = assign_ticket(db, ticket.id)
    assert result.status == "assigned"
    assert result.agent_id == anna.id
    assert result.assigned_at is not None
