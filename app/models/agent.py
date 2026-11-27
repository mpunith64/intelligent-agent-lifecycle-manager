from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional


class AgentLifecycleStatus(str, Enum):
    READY = "READY"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    UPGRADING = "UPGRADING"


class AgentHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    OFFLINE = "OFFLINE"


class Agent(BaseModel):

    agent_id: str

    agent_name: str

    lifecycle_status: AgentLifecycleStatus = (
        AgentLifecycleStatus.READY
    )

    health_status: AgentHealthStatus = (
        AgentHealthStatus.HEALTHY
    )

    active_sessions: int = 0

    version: str = "1.0.0"

    previous_version: Optional[str] = None

    last_heartbeat: Optional[datetime] = None

    registered_at: datetime

    drain_started_at: Optional[datetime] = None

    drain_reason: Optional[str] = None

    recovery_attempts: int = 0

    available_for_jobs: bool = True