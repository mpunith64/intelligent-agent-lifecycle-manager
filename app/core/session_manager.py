from datetime import datetime, timezone
import uuid

from app.core.agent_manager import agent_manager
from app.models.agent import AgentLifecycleStatus
from app.models.session import JobSession, SessionStatus
from app.monitoring.event_logger import event_logger


class SessionManager:

    def __init__(self, manager, logger):
        self.sessions: dict[str, JobSession] = {}
        self.agent_manager = manager
        self.event_logger = logger

    def submit_session(
        self,
        job_name: str,
        timeout_seconds: int = 3600,
        max_retries: int = 2,
        metadata: dict | None = None,
        auto_schedule: bool = True,
    ) -> JobSession:
        session_id = f"ses-{uuid.uuid4().hex[:12]}"
        session = JobSession(
            session_id=session_id,
            job_name=job_name,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self.sessions[session_id] = session
        self.event_logger.log_event(
            session_id,
            "SESSION_QUEUED",
            f"Job '{job_name}' queued",
        )
        if auto_schedule:
            self.schedule_pending()
        return session

    def schedule_pending(self) -> list[JobSession]:
        assigned: list[JobSession] = []
        pending = [
            s
            for s in self.sessions.values()
            if s.status in (SessionStatus.QUEUED, SessionStatus.REQUEUED)
        ]
        pending.sort(key=lambda s: s.created_at)

        for session in pending:
            available = self.agent_manager.get_available_agents()
            if not available:
                break
            agent = available[0]
            session.status = SessionStatus.RUNNING
            session.agent_id = agent.agent_id
            session.started_at = datetime.now(timezone.utc)
            agent.active_sessions += 1
            agent.lifecycle_status = AgentLifecycleStatus.BUSY
            self.agent_manager._update_availability(agent)

            self.event_logger.log_event(
                agent.agent_id,
                "SESSION_STARTED",
                f"Session {session.session_id} ({session.job_name}) started",
            )
            assigned.append(session)

        return assigned

    def get_all_sessions(self) -> list[JobSession]:
        return list(self.sessions.values())

    def get_session(self, session_id: str) -> JobSession | None:
        return self.sessions.get(session_id)

    def complete_session(
        self,
        session_id: str,
        exit_code: int = 0,
        error_message: str | None = None,
    ) -> JobSession:
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        session.exit_code = exit_code
        session.error_message = error_message
        session.finished_at = datetime.now(timezone.utc)
        session.status = (
            SessionStatus.COMPLETED if exit_code == 0 else SessionStatus.FAILED
        )
        self._release_agent(session)
        self.event_logger.log_event(
            session.agent_id or session.session_id,
            f"SESSION_{session.status.value}",
            f"Session {session.session_id} {session.status.value.lower()} (exit_code={exit_code})",
        )
        return session

    def cancel_session(
        self, session_id: str, reason: str = "Cancelled by user"
    ) -> JobSession:
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        session.status = SessionStatus.CANCELLED
        session.error_message = reason
        session.finished_at = datetime.now(timezone.utc)
        self._release_agent(session)
        self.event_logger.log_event(
            session.agent_id or session.session_id,
            "SESSION_CANCELLED",
            f"Session {session.session_id} cancelled: {reason}",
        )
        return session

    def requeue_session(self, session_id: str, reason: str) -> JobSession:
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session not found")

        self._release_agent(session)
        if session.retry_count < session.max_retries:
            session.retry_count += 1
            session.status = SessionStatus.REQUEUED
            session.agent_id = None
            session.started_at = None
            session.error_message = reason
            self.event_logger.log_event(
                session.session_id,
                "SESSION_REQUEUED",
                f"Session {session.session_id} requeued ({session.retry_count}/{session.max_retries}): {reason}",
            )
        else:
            session.status = SessionStatus.FAILED
            session.finished_at = datetime.now(timezone.utc)
            session.error_message = f"Max retries exceeded: {reason}"
            self.event_logger.log_event(
                session.session_id,
                "SESSION_FAILED",
                f"Session {session.session_id} failed: {session.error_message}",
            )
        return session

    def check_timeouts(self) -> list[JobSession]:
        now = datetime.now(timezone.utc)
        timed_out: list[JobSession] = []
        for session in list(self.sessions.values()):
            if session.status != SessionStatus.RUNNING or not session.started_at:
                continue
            elapsed = (now - session.started_at).total_seconds()
            if elapsed > session.timeout_seconds:
                self.requeue_session(
                    session.session_id,
                    f"Session timed out after {elapsed:.1f}s",
                )
                timed_out.append(session)
        return timed_out

    def _release_agent(self, session: JobSession) -> None:
        if not session.agent_id:
            return
        agent = self.agent_manager.get_agent(session.agent_id)
        if not agent:
            return
        if agent.active_sessions > 0:
            agent.active_sessions -= 1
        if (
            agent.lifecycle_status == AgentLifecycleStatus.BUSY
            and agent.active_sessions == 0
        ):
            agent.lifecycle_status = AgentLifecycleStatus.READY
        elif (
            agent.lifecycle_status == AgentLifecycleStatus.DRAINING
            and agent.active_sessions == 0
        ):
            self.event_logger.log_event(
                agent.agent_id,
                "AGENT_DRAINED",
                "Agent finished all active sessions during drain",
            )
        self.agent_manager._update_availability(agent)


session_manager = SessionManager(agent_manager, event_logger)
