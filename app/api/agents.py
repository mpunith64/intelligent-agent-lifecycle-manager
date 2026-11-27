from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.agent_manager import agent_manager
from app.core.recovery_manager import recovery_manager
from app.core.upgrade_manager import upgrade_manager
from app.monitoring.event_logger import event_logger


router = APIRouter(
    prefix="/agents",
    tags=["Agent Management"]
)


class AgentRegistrationRequest(BaseModel):

    agent_id: str = Field(min_length=1, max_length=100)

    agent_name: str = Field(min_length=1, max_length=100)


# ----------------------------------
# Register Agent
# ----------------------------------

@router.post("/register", status_code=201)
async def register_agent(request: AgentRegistrationRequest):

    try:

        return agent_manager.register_agent(
            request.agent_id,
            request.agent_name
        )

    except ValueError as error:

        raise HTTPException(
            status_code=409,
            detail=str(error)
        )


# ----------------------------------
# List Agents
# ----------------------------------

@router.get("/")
async def list_agents():

    return agent_manager.get_all_agents()


# ----------------------------------
# Overall Agent Health
# ----------------------------------

@router.get("/monitoring/health")
async def monitoring_health():

    return agent_manager.check_agent_health()


# ----------------------------------
# Health Summary
# ----------------------------------

@router.get("/monitoring/summary")
async def monitoring_summary():

    return agent_manager.get_health_summary()


# ----------------------------------
# Available Agents
# ----------------------------------

@router.get("/monitoring/available")
async def available_agents():

    return agent_manager.get_available_agents()


# ----------------------------------
# Agent Event History
# ----------------------------------

@router.get("/monitoring/events")
async def agent_events(
    agent_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000)
):

    events = event_logger.get_events(agent_id)

    return events[-limit:]


# ----------------------------------
# Individual Agent
# ----------------------------------

@router.get("/{agent_id}")
async def get_agent(agent_id: str):

    agent = agent_manager.get_agent(agent_id)

    if not agent:

        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    return agent


# ----------------------------------
# Agent Heartbeat
# ----------------------------------

@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str):

    try:

        return agent_manager.heartbeat(agent_id)

    except ValueError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error)
        )


# ----------------------------------
# Drain / Undrain / Upgrade / Recover
# ----------------------------------

@router.post("/{agent_id}/drain")
async def drain_agent(agent_id: str, reason: str = "maintenance"):
    try:
        return agent_manager.start_drain(agent_id, reason=reason)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/{agent_id}/undrain")
async def undrain_agent(agent_id: str):
    try:
        return agent_manager.undrain_agent(agent_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/{agent_id}/upgrade")
async def upgrade_agent(
    agent_id: str,
    target_version: str,
    simulate_failure: bool = False,
):
    try:
        return upgrade_manager.upgrade_agent(
            agent_id, target_version, simulate_failure=simulate_failure
        )
    except ValueError as error:
        detail = str(error)
        status = 404 if "not found" in detail.lower() else 409
        raise HTTPException(status_code=status, detail=detail)
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error))


@router.post("/{agent_id}/recover")
async def recover_agent(agent_id: str, max_attempts: int = 3):
    try:
        return recovery_manager.recover_agent(
            agent_id, max_attempts=max_attempts
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))


# ----------------------------------
# Individual Agent Health
# ----------------------------------

@router.get("/{agent_id}/health")
async def get_agent_health(agent_id: str):

    try:

        return agent_manager.get_agent_health(agent_id)

    except ValueError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error)
        )