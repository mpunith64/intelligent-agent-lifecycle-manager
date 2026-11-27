from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional


class AgentStatus(str, Enum):
    READY = "READY"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    OFFLINE = "OFFLINE"
    UPGRADING = "UPGRADING"


class Agent(BaseModel):
    agent_id: str
    agent_name: str
    status: AgentStatus = AgentStatus.READY
    active_sessions: int = 0
    version: str = "1.0.0"
    last_heartbeat: Optional[datetime] = None