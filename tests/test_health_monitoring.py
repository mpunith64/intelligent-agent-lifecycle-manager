import time

import pytest

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():

    with TestClient(app) as test_client:

        yield test_client


def register_agent(client, agent_id):

    return client.post(
        "/agents/register",
        json={
            "agent_id": agent_id,
            "agent_name": f"build-{agent_id}"
        }
    )


def test_agent_registration(client):

    response = register_agent(client, "test-agent-001")

    assert response.status_code == 201

    assert response.json()["health_status"] == "HEALTHY"


def test_duplicate_registration(client):

    register_agent(client, "test-agent-002")

    response = register_agent(client, "test-agent-002")

    assert response.status_code == 409


def test_heartbeat(client):

    register_agent(client, "test-agent-003")

    response = client.post(
        "/agents/test-agent-003/heartbeat"
    )

    assert response.status_code == 200

    assert response.json()["health_status"] == "HEALTHY"


def test_unknown_agent_heartbeat(client):

    response = client.post(
        "/agents/unknown-agent/heartbeat"
    )

    assert response.status_code == 404


def test_offline_detection(client):

    register_agent(client, "test-agent-004")

    from app.core.agent_manager import agent_manager

    # Force an old heartbeat for deterministic testing.
    agent = agent_manager.get_agent("test-agent-004")

    from datetime import datetime, timedelta, timezone

    agent.last_heartbeat = (
        datetime.now(timezone.utc) - timedelta(seconds=60)
    )

    response = client.get("/agents/monitoring/health")

    assert response.status_code == 200

    assert (
        agent_manager.get_agent("test-agent-004").health_status.value
        == "OFFLINE"
    )


def test_agent_recovery(client):

    register_agent(client, "test-agent-005")

    from app.core.agent_manager import agent_manager

    agent = agent_manager.get_agent("test-agent-005")

    from datetime import datetime, timedelta, timezone

    agent.last_heartbeat = (
        datetime.now(timezone.utc) - timedelta(seconds=60)
    )

    agent_manager.check_agent_health(timeout_seconds=15)

    response = client.post(
        "/agents/test-agent-005/heartbeat"
    )

    assert response.status_code == 200

    assert response.json()["health_status"] == "HEALTHY"


def test_health_summary(client):

    register_agent(client, "test-agent-006")

    response = client.get(
        "/agents/monitoring/summary"
    )

    assert response.status_code == 200

    assert response.json()["total_agents"] >= 1


def test_available_agents(client):

    register_agent(client, "test-agent-007")

    response = client.get(
        "/agents/monitoring/available"
    )

    assert response.status_code == 200