from app.assignment import choose_agent
from app.models import Agent, Ticket

def test_choose_agent_prefers_matching_skill(db_session):
    network = Agent(name="Network specialist", skills="network")
    software = Agent(name="Software specialist", skills="software")
    db_session.add_all([network, software])
    db_session.commit()
    chosen = choose_agent(db_session, "network")
    assert chosen.name == "Network specialist"

def test_choose_agent_returns_none_when_no_active_agents(db_session):
    db_session.add(Agent(name="Inactive", skills="general", is_active=False))
    db_session.commit()
    assert choose_agent(db_session, "general") is None
