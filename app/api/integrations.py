import os
from fastapi import APIRouter, Header, HTTPException, Request

from app.integrations.github_actions import github_actions


router = APIRouter(
    prefix="/integrations/github",
    tags=["GitHub Actions Integration"]
)


@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default="workflow_job"),
    x_hub_signature_256: str | None = Header(default=None),
):
    body = await request.body()
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if secret and not github_actions.verify_signature(
        body, x_hub_signature_256, secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    if x_github_event == "workflow_job":
        return github_actions.handle_workflow_job(payload)

    return {"status": "ignored", "event": x_github_event}


@router.get("/runners")
async def list_github_runners():
    return {"runners": github_actions.get_runner_status()}
