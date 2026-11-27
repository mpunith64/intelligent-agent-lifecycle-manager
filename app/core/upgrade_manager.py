from datetime import datetime, timezone
import uuid

from app.core.agent_manager import agent_manager
from app.models.agent import Agent, AgentHealthStatus, AgentLifecycleStatus
from app.models.upgrade import UpgradePlan, UpgradeStatus
from app.monitoring.event_logger import event_logger


class UpgradeManager:

    def __init__(self, manager, logger):
        self.plans: dict[str, UpgradePlan] = {}
        self.agent_manager = manager
        self.event_logger = logger

    # ----------------------------------
    # Phase 5: Single-Agent Upgrade
    # ----------------------------------

    def upgrade_agent(
        self,
        agent_id: str,
        target_version: str,
        simulate_failure: bool = False,
    ) -> Agent:
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            raise ValueError("Agent not found")

        if agent.health_status == AgentHealthStatus.OFFLINE:
            raise ValueError("Cannot upgrade an offline agent")

        if agent.active_sessions > 0:
            self.agent_manager.start_drain(
                agent_id, reason=f"upgrade to {target_version}"
            )
            return agent

        agent.previous_version = agent.version
        agent.lifecycle_status = AgentLifecycleStatus.UPGRADING
        self.agent_manager._update_availability(agent)
        self.event_logger.log_event(
            agent_id,
            "AGENT_UPGRADING",
            f"Upgrading agent from {agent.previous_version} to {target_version}",
        )

        if simulate_failure:
            agent.health_status = AgentHealthStatus.UNHEALTHY
            agent.lifecycle_status = AgentLifecycleStatus.READY
            agent.version = agent.previous_version
            self.agent_manager._update_availability(agent)
            self.event_logger.log_event(
                agent_id,
                "AGENT_UPGRADE_FAILED",
                f"Upgrade to {target_version} failed health check; reverted to {agent.version}",
            )
            raise RuntimeError(f"Upgrade to {target_version} failed health check")

        agent.version = target_version
        agent.lifecycle_status = AgentLifecycleStatus.READY
        agent.health_status = AgentHealthStatus.HEALTHY
        agent.drain_started_at = None
        agent.drain_reason = None
        self.agent_manager._update_availability(agent)
        self.event_logger.log_event(
            agent_id,
            "AGENT_UPGRADED",
            f"Agent upgraded successfully to {target_version}",
        )
        return agent

    # ----------------------------------
    # Phase 6: Rolling Upgrade Plans
    # ----------------------------------

    def create_rolling_upgrade(
        self,
        target_version: str,
        batch_size: int = 1,
        max_unavailable: int = 1,
        auto_rollback: bool = True,
        agent_ids: list[str] | None = None,
    ) -> UpgradePlan:
        if batch_size <= 0 or max_unavailable <= 0:
            raise ValueError("batch_size and max_unavailable must be positive")

        if agent_ids is not None:
            targets = [
                self.agent_manager.get_agent(aid)
                for aid in agent_ids
                if self.agent_manager.get_agent(aid) is not None
            ]
        else:
            targets = [
                a
                for a in self.agent_manager.get_all_agents()
                if a.version != target_version
                and a.health_status != AgentHealthStatus.OFFLINE
            ]

        now = datetime.now(timezone.utc)
        plan_id = f"upg-{uuid.uuid4().hex[:12]}"
        plan = UpgradePlan(
            plan_id=plan_id,
            target_version=target_version,
            batch_size=batch_size,
            max_unavailable=max_unavailable,
            auto_rollback=auto_rollback,
            status=UpgradeStatus.IN_PROGRESS if targets else UpgradeStatus.COMPLETED,
            target_agents=[a.agent_id for a in targets],
            previous_versions={a.agent_id: a.version for a in targets},
            created_at=now,
            updated_at=now,
        )
        self.plans[plan_id] = plan
        self.event_logger.log_event(
            plan_id,
            "ROLLING_UPGRADE_STARTED",
            f"Rolling upgrade to {target_version} created for {len(targets)} agents",
        )
        return plan

    def advance_upgrade(
        self,
        plan_id: str,
        simulate_failure_agents: set[str] | None = None,
    ) -> UpgradePlan:
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError("Upgrade plan not found")

        if plan.status in (
            UpgradeStatus.COMPLETED,
            UpgradeStatus.ROLLED_BACK,
            UpgradeStatus.FAILED,
        ):
            return plan

        sim_fail = simulate_failure_agents or set()
        remaining = [
            aid
            for aid in plan.target_agents
            if aid not in plan.upgraded_agents and aid not in plan.failed_agents
        ]

        limit = min(plan.batch_size, plan.max_unavailable)
        batch = remaining[:limit]

        for aid in batch:
            try:
                agent = self.upgrade_agent(
                    aid,
                    plan.target_version,
                    simulate_failure=(aid in sim_fail),
                )
                if agent.version == plan.target_version:
                    plan.upgraded_agents.append(aid)
            except Exception as exc:
                plan.failed_agents.append(aid)
                plan.error_message = str(exc)
                plan.updated_at = datetime.now(timezone.utc)
                if plan.auto_rollback:
                    return self.rollback_upgrade(
                        plan_id, reason=f"Auto-rollback triggered by {aid}: {exc}"
                    )
                plan.status = UpgradeStatus.FAILED
                return plan

        plan.updated_at = datetime.now(timezone.utc)
        if len(plan.upgraded_agents) == len(plan.target_agents):
            plan.status = UpgradeStatus.COMPLETED
            self.event_logger.log_event(
                plan_id,
                "ROLLING_UPGRADE_COMPLETED",
                f"Rolling upgrade to {plan.target_version} completed",
            )
        return plan

    # ----------------------------------
    # Phase 7: Upgrade Rollback
    # ----------------------------------

    def rollback_upgrade(
        self, plan_id: str, reason: str = "Manual rollback"
    ) -> UpgradePlan:
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError("Upgrade plan not found")

        for aid in set(plan.upgraded_agents + plan.failed_agents):
            agent = self.agent_manager.get_agent(aid)
            if not agent:
                continue
            prev = plan.previous_versions.get(aid)
            if prev:
                agent.version = prev
            agent.lifecycle_status = AgentLifecycleStatus.READY
            if agent.health_status == AgentHealthStatus.UNHEALTHY:
                agent.health_status = AgentHealthStatus.HEALTHY
            self.agent_manager._update_availability(agent)

        plan.status = UpgradeStatus.ROLLED_BACK
        plan.error_message = reason
        plan.updated_at = datetime.now(timezone.utc)
        self.event_logger.log_event(
            plan_id,
            "ROLLING_UPGRADE_ROLLED_BACK",
            f"Rolling upgrade rolled back: {reason}",
        )
        return plan

    def get_plan(self, plan_id: str) -> UpgradePlan | None:
        return self.plans.get(plan_id)

    def get_all_plans(self) -> list[UpgradePlan]:
        return list(self.plans.values())


upgrade_manager = UpgradeManager(agent_manager, event_logger)
