from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REQUEUED = "REQUEUED"


class JobSession(BaseModel):
    session_id: str
    job_name: str
    agent_id: Optional[str] = None
    status: SessionStatus = SessionStatus.QUEUED
    timeout_seconds: int = 3600
    max_retries: int = 2
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
