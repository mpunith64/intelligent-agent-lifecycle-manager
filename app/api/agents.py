from fastapi import APIRouter, HTTPException
from app.core.agent_manager import agent_manager

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("/register")
async def register_agent(agent_id: str, agent_name: str):

    try:
        return agent_manager.register_agent(agent_id, agent_name)

    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get("/")
async def list_agents():
    return agent_manager.get_all_agents()


@router.get("/{agent_id}")
async def get_agent(agent_id: str):

    agent = agent_manager.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent