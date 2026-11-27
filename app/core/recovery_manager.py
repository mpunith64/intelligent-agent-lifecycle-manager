from datetime import datetime, timezone

from app.core.agent_manager import agent_manager
from app.core.session_manager import session_manager
from app.models.agent import AgentHealthStatus, AgentLifecycleStatus
from app.models.session import SessionStatus
from app.monitoring.event_logger import event_logger


class RecoveryManager:

    def __init__(self, a_manager, s_manager, logger):
        self.agent_manager = a_manager
        self.session_manager = s_manager
        self.event_logger = logger

    def recover_orphaned_sessions(self) -> list[str]:
        requeued_ids: list[str] = []
        for session in list(self.session_manager.get_all_sessions()):
            if session.status != SessionStatus.RUNNING:
                continue
            agent = (
                self.agent_manager.get_agent(session.agent_id)
                if session.agent_id
                else None
            )
            if agent is None or agent.health_status in (
                AgentHealthStatus.OFFLINE,
                AgentHealthStatus.UNHEALTHY,
            ):
                self.session_manager.requeue_session(
                    session.session_id,
                    f"Agent {session.agent_id} became {agent.health_status.value if agent else 'MISSING'}",
                )
                requeued_ids.append(session.session_id)

        if requeued_ids:
            self.session_manager.schedule_pending()
        return requeued_ids

    def recover_agent(self, agent_id: str, max_attempts: int = 3):
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            raise ValueError("Agent not found")

        if agent.health_status == AgentHealthStatus.HEALTHY:
            return agent

        agent.recovery_attempts += 1
        if agent.recovery_attempts > max_attempts:
            self.event_logger.log_event(
                agent_id,
                "AGENT_RECOVERY_EXHAUSTED",
                f"Recovery failed after {max_attempts} attempts",
            )
            raise RuntimeError(
                f"Agent {agent_id} exceeded max recovery attempts ({max_attempts})"
            )

        agent.health_status = AgentHealthStatus.HEALTHY
        agent.lifecycle_status = (
            AgentLifecycleStatus.BUSY
            if agent.active_sessions > 0
            else AgentLifecycleStatus.READY
        )
        agent.last_heartbeat = datetime.now(timezone.utc)
        self.agent_manager._update_availability(agent)
        self.event_logger.log_event(
            agent_id,
            "AGENT_RECOVERED",
            f"Agent recovered on attempt {agent.recovery_attempts}",
        )
        return agent

    def reconcile_all(self, drain_timeout_seconds: int = 300) -> dict:
        drain_res = self.agent_manager.reconcile_draining(
            timeout_seconds=drain_timeout_seconds
        )
        for aid in drain_res["timed_out"]:
            for session in list(self.session_manager.get_all_sessions()):
                if (
                    session.status == SessionStatus.RUNNING
                    and session.agent_id == aid
                ):
                    self.session_manager.requeue_session(
                        session.session_id,
                        f"Agent {aid} drain timeout exceeded",
                    )

        timed_out_sessions = self.session_manager.check_timeouts()
        orphaned = self.recover_orphaned_sessions()
        scheduled = self.session_manager.schedule_pending()

        return {
            "drained_agents": drain_res["drained"],
            "drain_timed_out_agents": drain_res["timed_out"],
            "timed_out_sessions": [s.session_id for s in timed_out_sessions],
            "requeued_orphaned_sessions": orphaned,
            "scheduled_sessions": [s.session_id for s in scheduled],
        }


recovery_manager = RecoveryManager(agent_manager, session_manager, event_logger)
