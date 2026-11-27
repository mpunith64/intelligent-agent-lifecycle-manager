from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.recovery_manager import recovery_manager
from app.core.upgrade_manager import upgrade_manager


router = APIRouter(
    tags=["Upgrades & Recovery"]
)


class RollingUpgradeRequest(BaseModel):
    target_version: str = Field(min_length=1, max_length=50)
    batch_size: int = Field(default=1, ge=1)
    max_unavailable: int = Field(default=1, ge=1)
    auto_rollback: bool = True
    agent_ids: list[str] | None = None


class AdvanceUpgradeRequest(BaseModel):
    simulate_failure_agents: list[str] = Field(default_factory=list)


class RollbackRequest(BaseModel):
    reason: str = "Manual rollback"


@router.post("/upgrades/rolling", status_code=201)
async def create_rolling_upgrade(request: RollingUpgradeRequest):
    try:
        return upgrade_manager.create_rolling_upgrade(
            target_version=request.target_version,
            batch_size=request.batch_size,
            max_unavailable=request.max_unavailable,
            auto_rollback=request.auto_rollback,
            agent_ids=request.agent_ids,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/upgrades/")
async def list_upgrades():
    return upgrade_manager.get_all_plans()


@router.get("/upgrades/{plan_id}")
async def get_upgrade(plan_id: str):
    plan = upgrade_manager.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Upgrade plan not found")
    return plan


@router.post("/upgrades/{plan_id}/advance")
async def advance_upgrade(
    plan_id: str,
    request: AdvanceUpgradeRequest | None = None,
):
    req = request or AdvanceUpgradeRequest()
    try:
        return upgrade_manager.advance_upgrade(
            plan_id,
            simulate_failure_agents=set(req.simulate_failure_agents),
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/upgrades/{plan_id}/rollback")
async def rollback_upgrade(
    plan_id: str,
    request: RollbackRequest | None = None,
):
    req = request or RollbackRequest()
    try:
        return upgrade_manager.rollback_upgrade(plan_id, reason=req.reason)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/recovery/reconcile")
async def reconcile_pool(drain_timeout_seconds: int = 300):
    return recovery_manager.reconcile_all(
        drain_timeout_seconds=drain_timeout_seconds
    )
