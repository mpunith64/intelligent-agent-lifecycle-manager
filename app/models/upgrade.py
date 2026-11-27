from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UpgradeStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class UpgradePlan(BaseModel):
    plan_id: str
    target_version: str
    batch_size: int = 1
    max_unavailable: int = 1
    auto_rollback: bool = True
    status: UpgradeStatus = UpgradeStatus.PENDING
    target_agents: list[str] = Field(default_factory=list)
    upgraded_agents: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(default_factory=list)
    previous_versions: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
