from datetime import datetime, timezone

from app.models.agent import (
    Agent,
    AgentLifecycleStatus,
    AgentHealthStatus
)

from app.monitoring.event_logger import event_logger


class AgentManager:

    def __init__(self, event_logger):

        self.agents = {}

        self.event_logger = event_logger

    # ----------------------------------
    # Register Agent
    # ----------------------------------

    def register_agent(self, agent_id, agent_name):

        if agent_id in self.agents:

            raise ValueError("Agent already registered")

        current_time = datetime.now(timezone.utc)

        agent = Agent(
            agent_id=agent_id,
            agent_name=agent_name,
            lifecycle_status=AgentLifecycleStatus.READY,
            health_status=AgentHealthStatus.HEALTHY,
            active_sessions=0,
            version="1.0.0",
            last_heartbeat=current_time,
            registered_at=current_time,
            available_for_jobs=True
        )

        self.agents[agent_id] = agent

        self.event_logger.log_event(
            agent_id,
            "AGENT_REGISTERED",
            "Agent successfully registered"
        )

        return agent

    # ----------------------------------
    # Get All Agents
    # ----------------------------------

    def get_all_agents(self):

        return list(self.agents.values())

    # ----------------------------------
    # Get Individual Agent
    # ----------------------------------

    def get_agent(self, agent_id):

        return self.agents.get(agent_id)

    # ----------------------------------
    # Update Heartbeat
    # ----------------------------------

    def heartbeat(self, agent_id):

        agent = self.agents.get(agent_id)

        if not agent:

            raise ValueError("Agent not found")

        previous_health = agent.health_status

        agent.last_heartbeat = datetime.now(timezone.utc)

        if previous_health != AgentHealthStatus.HEALTHY:

            agent.health_status = AgentHealthStatus.HEALTHY

            self.event_logger.log_event(
                agent_id,
                "AGENT_RECOVERED",
                "Agent heartbeat restored"
            )

        self._update_availability(agent)

        self.event_logger.log_event(
            agent_id,
            "HEARTBEAT_RECEIVED",
            "Agent heartbeat received"
        )

        return agent

    # ----------------------------------
    # Check Agent Health
    # ----------------------------------

    def check_agent_health(self, timeout_seconds=15):

        if timeout_seconds <= 0:

            raise ValueError(
                "Timeout must be greater than zero"
            )

        current_time = datetime.now(timezone.utc)

        for agent in self.agents.values():

            if not agent.last_heartbeat:

                elapsed = float("inf")

            else:

                elapsed = (
                    current_time - agent.last_heartbeat
                ).total_seconds()

            if elapsed > timeout_seconds:

                if agent.health_status != AgentHealthStatus.OFFLINE:

                    agent.health_status = AgentHealthStatus.OFFLINE

                    self.event_logger.log_event(
                        agent.agent_id,
                        "AGENT_OFFLINE",
                        "Heartbeat timeout exceeded"
                    )

            self._update_availability(agent)

        return self.get_all_agents()

    # ----------------------------------
    # Agent Availability
    # ----------------------------------

    def _update_availability(self, agent):

        agent.available_for_jobs = (
            agent.health_status == AgentHealthStatus.HEALTHY
            and agent.lifecycle_status == AgentLifecycleStatus.READY
        )

    # ----------------------------------
    # Get Available Agents
    # ----------------------------------

    def get_available_agents(self):

        return [
            agent for agent in self.agents.values()
            if agent.available_for_jobs
        ]

    # ----------------------------------
    # Individual Agent Health
    # ----------------------------------

    def get_agent_health(self, agent_id):

        agent = self.agents.get(agent_id)

        if not agent:

            raise ValueError("Agent not found")

        return {
            "agent_id": agent.agent_id,
            "lifecycle_status": agent.lifecycle_status,
            "health_status": agent.health_status,
            "last_heartbeat": agent.last_heartbeat,
            "available_for_jobs": agent.available_for_jobs
        }

    # ----------------------------------
    # Health Summary
    # ----------------------------------

    def get_health_summary(self):

        agents = list(self.agents.values())

        return {
            "total_agents": len(agents),

            "healthy": sum(
                a.health_status == AgentHealthStatus.HEALTHY
                for a in agents
            ),

            "unhealthy": sum(
                a.health_status == AgentHealthStatus.UNHEALTHY
                for a in agents
            ),

            "offline": sum(
                a.health_status == AgentHealthStatus.OFFLINE
                for a in agents
            ),

            "available": sum(
                a.available_for_jobs
                for a in agents
            ),

            "busy": sum(
                a.lifecycle_status == AgentLifecycleStatus.BUSY
                for a in agents
            ),

            "draining": sum(
                a.lifecycle_status == AgentLifecycleStatus.DRAINING
                for a in agents
            ),

            "upgrading": sum(
                a.lifecycle_status == AgentLifecycleStatus.UPGRADING
                for a in agents
            )
        }


    # ----------------------------------
    # Graceful Draining
    # ----------------------------------

    def start_drain(self, agent_id: str, reason: str = "maintenance"):

        agent = self.agents.get(agent_id)

        if not agent:
            raise ValueError("Agent not found")

        agent.lifecycle_status = AgentLifecycleStatus.DRAINING
        agent.drain_started_at = datetime.now(timezone.utc)
        agent.drain_reason = reason
        self._update_availability(agent)

        self.event_logger.log_event(
            agent_id,
            "AGENT_DRAINING",
            f"Agent draining started ({reason})"
        )

        return agent

    def undrain_agent(self, agent_id: str):

        agent = self.agents.get(agent_id)

        if not agent:
            raise ValueError("Agent not found")

        agent.lifecycle_status = (
            AgentLifecycleStatus.BUSY
            if agent.active_sessions > 0
            else AgentLifecycleStatus.READY
        )
        agent.drain_started_at = None
        agent.drain_reason = None
        self._update_availability(agent)

        self.event_logger.log_event(
            agent_id,
            "AGENT_UNDRAINED",
            "Agent returned to active pool"
        )

        return agent

    def reconcile_draining(self, timeout_seconds: int = 300):

        now = datetime.now(timezone.utc)
        drained = []
        timed_out = []

        for agent in self.agents.values():
            if agent.lifecycle_status != AgentLifecycleStatus.DRAINING:
                continue

            if agent.active_sessions == 0:
                drained.append(agent.agent_id)
                continue

            if agent.drain_started_at:
                elapsed = (now - agent.drain_started_at).total_seconds()
                if elapsed > timeout_seconds:
                    timed_out.append(agent.agent_id)

        return {"drained": drained, "timed_out": timed_out}


agent_manager = AgentManager(event_logger)