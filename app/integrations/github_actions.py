import hashlib
import hmac
from typing import Any

from app.core.agent_manager import agent_manager
from app.core.session_manager import session_manager
from app.models.agent import AgentHealthStatus, AgentLifecycleStatus
from app.monitoring.event_logger import event_logger


class GitHubActionsIntegration:

    def __init__(self, a_manager, s_manager, logger):
        self.agent_manager = a_manager
        self.session_manager = s_manager
        self.event_logger = logger
        self.job_to_session: dict[int, str] = {}

    @staticmethod
    def verify_signature(
        payload_bytes: bytes, signature_header: str | None, secret: str
    ) -> bool:
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(
            secret.encode("utf-8"), payload_bytes, hashlib.sha256
        ).hexdigest()
        received = signature_header.split("=", 1)[1]
        return hmac.compare_digest(expected, received)

    def handle_workflow_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        job = payload.get("workflow_job") or {}
        job_id = job.get("id")
        job_name = job.get("name") or f"github-job-{job_id}"
        repo = (payload.get("repository") or {}).get("full_name", "unknown/repo")

        if action == "queued":
            session = self.session_manager.submit_session(
                job_name=job_name,
                metadata={
                    "source": "github_actions",
                    "github_job_id": job_id,
                    "repository": repo,
                    "labels": job.get("labels", []),
                },
            )
            if job_id is not None:
                self.job_to_session[int(job_id)] = session.session_id
            self.event_logger.log_event(
                session.session_id,
                "GITHUB_JOB_QUEUED",
                f"GitHub Actions job '{job_name}' ({repo}) mapped to {session.session_id}",
            )
            return {"status": "queued", "session": session}

        if action == "in_progress":
            session_id = (
                self.job_to_session.get(int(job_id))
                if job_id is not None
                else None
            )
            self.event_logger.log_event(
                session_id or str(job_id),
                "GITHUB_JOB_IN_PROGRESS",
                f"GitHub Actions job '{job_name}' running",
            )
            return {"status": "in_progress", "session_id": session_id}

        if action == "completed":
            session_id = (
                self.job_to_session.get(int(job_id))
                if job_id is not None
                else None
            )
            if session_id and self.session_manager.get_session(session_id):
                conclusion = job.get("conclusion", "success")
                exit_code = 0 if conclusion == "success" else 1
                session = self.session_manager.complete_session(
                    session_id,
                    exit_code=exit_code,
                    error_message=None if exit_code == 0 else f"GitHub job {conclusion}",
                )
                return {"status": "completed", "session": session}
            return {"status": "ignored", "reason": "No matching session"}

        return {"status": "ignored", "action": action}

    def get_runner_status(self) -> list[dict[str, Any]]:
        runners = []
        for agent in self.agent_manager.get_all_agents():
            runners.append(
                {
                    "id": agent.agent_id,
                    "name": agent.agent_name,
                    "os": "linux",
                    "status": (
                        "offline"
                        if agent.health_status == AgentHealthStatus.OFFLINE
                        else "online"
                    ),
                    "busy": agent.lifecycle_status == AgentLifecycleStatus.BUSY
                    or agent.active_sessions > 0,
                    "lifecycle_status": agent.lifecycle_status.value,
                    "health_status": agent.health_status.value,
                    "version": agent.version,
                }
            )
        return runners


github_actions = GitHubActionsIntegration(
    agent_manager, session_manager, event_logger
)
