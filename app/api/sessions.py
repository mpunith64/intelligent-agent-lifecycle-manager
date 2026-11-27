from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.session_manager import session_manager


router = APIRouter(
    prefix="/sessions",
    tags=["Session Management"]
)


class SessionSubmitRequest(BaseModel):
    job_name: str = Field(min_length=1, max_length=200)
    timeout_seconds: int = Field(default=3600, gt=0)
    max_retries: int = Field(default=2, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_schedule: bool = True


class SessionCompleteRequest(BaseModel):
    exit_code: int = 0
    error_message: str | None = None


@router.post("/submit", status_code=201)
async def submit_session(request: SessionSubmitRequest):
    return session_manager.submit_session(
        job_name=request.job_name,
        timeout_seconds=request.timeout_seconds,
        max_retries=request.max_retries,
        metadata=request.metadata,
        auto_schedule=request.auto_schedule,
    )


@router.post("/schedule")
async def schedule_pending():
    assigned = session_manager.schedule_pending()
    return {"scheduled_count": len(assigned), "sessions": assigned}


@router.get("/")
async def list_sessions():
    return session_manager.get_all_sessions()


@router.get("/{session_id}")
async def get_session(session_id: str):
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/complete")
async def complete_session(
    session_id: str,
    request: SessionCompleteRequest | None = None,
):
    req = request or SessionCompleteRequest()
    try:
        return session_manager.complete_session(
            session_id=session_id,
            exit_code=req.exit_code,
            error_message=req.error_message,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str, reason: str = "Cancelled by user"):
    try:
        return session_manager.cancel_session(session_id=session_id, reason=reason)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
