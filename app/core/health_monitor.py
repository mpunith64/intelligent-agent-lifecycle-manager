import asyncio
import logging


logger = logging.getLogger(__name__)


class HealthMonitor:

    def __init__(
        self,
        agent_manager,
        timeout_seconds=15,
        monitoring_interval=5
    ):

        self.agent_manager = agent_manager

        self.timeout_seconds = timeout_seconds

        self.monitoring_interval = monitoring_interval

        self.running = False

    async def start(self):

        self.running = True

        logger.info("Agent health monitor started")

        while self.running:

            try:

                self.agent_manager.check_agent_health(
                    timeout_seconds=self.timeout_seconds
                )
                from app.core.recovery_manager import recovery_manager

                recovery_manager.reconcile_all()

            except Exception:

                logger.exception(
                    "Error during agent health monitoring"
                )

            await asyncio.sleep(
                self.monitoring_interval
            )

    def stop(self):

        self.running = False

        logger.info("Agent health monitor stopped")