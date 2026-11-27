import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml

from fastapi import FastAPI

from app.api.agents import router as agent_router
from app.api.dashboard import router as dashboard_router
from app.api.integrations import router as integration_router
from app.api.sessions import router as session_router
from app.api.upgrades import router as upgrade_router

from app.core.agent_manager import agent_manager

from app.core.health_monitor import HealthMonitor


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# ----------------------------------
# Load Configuration
# ----------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as file:

    config = yaml.safe_load(file)


heartbeat_config = config["heartbeat"]

monitoring_config = config["monitoring"]


# ----------------------------------
# Initialize Health Monitor
# ----------------------------------

health_monitor = HealthMonitor(
    agent_manager=agent_manager,
    timeout_seconds=heartbeat_config["timeout_seconds"],
    monitoring_interval=heartbeat_config[
        "monitoring_interval_seconds"
    ]
)


# ----------------------------------
# Application Lifecycle
# ----------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    monitor_task = None

    if monitoring_config["enabled"]:

        monitor_task = asyncio.create_task(
            health_monitor.start()
        )

    logging.info("Agent Lifecycle Manager started")

    yield

    health_monitor.stop()

    if monitor_task:

        monitor_task.cancel()

        try:
            await monitor_task

        except asyncio.CancelledError:
            pass

    logging.info("Agent Lifecycle Manager stopped")


# ----------------------------------
# FastAPI Application
# ----------------------------------

app = FastAPI(
    title="Intelligent Agent Lifecycle Manager",
    description=(
        "CI/CD Agent Lifecycle Management, Session Tracking, "
        "Graceful Draining, Rolling Upgrades, Failure Recovery, "
        "Monitoring Dashboard & GitHub Actions Integration"
    ),
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():

    return {
        "project": "Intelligent Agent Lifecycle Manager",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }


app.include_router(agent_router)
app.include_router(session_router)
app.include_router(upgrade_router)
app.include_router(integration_router)
app.include_router(dashboard_router)