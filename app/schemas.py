from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=10000)
    category: str = Field(default="general", min_length=2, max_length=80)
    priority: int = Field(default=3, ge=1, le=5, description="1 — наивысший приоритет, 5 — низший")

class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    skills: str
    is_active: bool

class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    priority: int
    status: str
    agent_id: int | None
    agent_name: str | None = None
    created_at: datetime
    assigned_at: datetime | None
