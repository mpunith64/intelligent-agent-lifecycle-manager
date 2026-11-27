from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.core.agent_manager import agent_manager
from app.core.session_manager import session_manager
from app.core.upgrade_manager import upgrade_manager
from app.integrations.github_actions import github_actions
from app.main import app
from app.models.agent import AgentHealthStatus
from app.monitoring.event_logger import event_logger


@pytest.fixture(autouse=True)
def clean_state():
    agent_manager.agents.clear()
    session_manager.sessions.clear()
    upgrade_manager.plans.clear()
    github_actions.job_to_session.clear()
    event_logger.events.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register(client, agent_id, name=None):
    return client.post(
        "/agents/register",
        json={"agent_id": agent_id, "agent_name": name or f"runner-{agent_id}"},
    )


# --- Phase 3: Session Management & Job Scheduling ---


def test_session_submit_schedule_and_complete(client):
    _register(client, "p3-agent-1")

    res = client.post("/sessions/submit", json={"job_name": "build-backend"})
    assert res.status_code == 201
    session = res.json()
    assert session["status"] == "RUNNING"
    assert session["agent_id"] == "p3-agent-1"

    agent = client.get("/agents/p3-agent-1").json()
    assert agent["lifecycle_status"] == "BUSY"
    assert agent["active_sessions"] == 1
    assert agent["available_for_jobs"] is False

    done = client.post(
        f"/sessions/{session['session_id']}/complete",
        json={"exit_code": 0},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "COMPLETED"

    agent_after = client.get("/agents/p3-agent-1").json()
    assert agent_after["lifecycle_status"] == "READY"
    assert agent_after["active_sessions"] == 0
    assert agent_after["available_for_jobs"] is True


# --- Phase 4: Graceful Agent Draining ---


def test_graceful_draining_blocks_new_jobs_and_completes_inflight(client):
    _register(client, "p4-agent-1")
    job1 = client.post("/sessions/submit", json={"job_name": "job-1"}).json()

    drain_res = client.post("/agents/p4-agent-1/drain?reason=maintenance")
    assert drain_res.status_code == 200
    assert drain_res.json()["lifecycle_status"] == "DRAINING"
    assert drain_res.json()["available_for_jobs"] is False

    # New job stays QUEUED because agent is draining
    job2 = client.post("/sessions/submit", json={"job_name": "job-2"}).json()
    assert job2["status"] == "QUEUED"

    # In-flight job finishes gracefully
    client.post(f"/sessions/{job1['session_id']}/complete", json={"exit_code": 0})
    assert client.get("/agents/p4-agent-1").json()["active_sessions"] == 0

    # Undrain returns agent to pool and schedules queued job
    undrain_res = client.post("/agents/p4-agent-1/undrain")
    assert undrain_res.status_code == 200
    assert undrain_res.json()["lifecycle_status"] == "READY"
    client.post("/sessions/schedule")
    assert client.get(f"/sessions/{job2['session_id']}").json()["status"] == "RUNNING"


# --- Phase 5: Automated Agent Upgrades ---


def test_single_agent_upgrade_and_drain_on_busy(client):
    _register(client, "p5-agent-1")
    job = client.post("/sessions/submit", json={"job_name": "long-job"}).json()

    # Busy agent transitions to DRAINING when upgrade is requested
    res1 = client.post("/agents/p5-agent-1/upgrade?target_version=2.0.0")
    assert res1.status_code == 200
    assert res1.json()["lifecycle_status"] == "DRAINING"

    client.post(f"/sessions/{job['session_id']}/complete", json={"exit_code": 0})

    # Now idle -> upgrades cleanly to 2.0.0
    res2 = client.post("/agents/p5-agent-1/upgrade?target_version=2.0.0")
    assert res2.status_code == 200
    assert res2.json()["version"] == "2.0.0"
    assert res2.json()["previous_version"] == "1.0.0"
    assert res2.json()["lifecycle_status"] == "READY"


# --- Phase 6: Rolling Agent Upgrades ---


def test_rolling_upgrade_in_batches(client):
    _register(client, "p6-a1")
    _register(client, "p6-a2")
    _register(client, "p6-a3")

    plan = client.post(
        "/upgrades/rolling",
        json={"target_version": "2.1.0", "batch_size": 2, "max_unavailable": 2},
    ).json()
    assert plan["status"] == "IN_PROGRESS"
    assert len(plan["target_agents"]) == 3

    step1 = client.post(f"/upgrades/{plan['plan_id']}/advance").json()
    assert len(step1["upgraded_agents"]) == 2
    assert step1["status"] == "IN_PROGRESS"

    step2 = client.post(f"/upgrades/{plan['plan_id']}/advance").json()
    assert len(step2["upgraded_agents"]) == 3
    assert step2["status"] == "COMPLETED"
    assert client.get("/agents/p6-a3").json()["version"] == "2.1.0"


# --- Phase 7: Failure Recovery & Rollback ---


def test_rolling_upgrade_auto_rollback_on_failure(client):
    _register(client, "p7-a1")
    _register(client, "p7-a2")

    plan = client.post(
        "/upgrades/rolling",
        json={
            "target_version": "3.0.0-bad",
            "batch_size": 2,
            "max_unavailable": 2,
            "auto_rollback": True,
        },
    ).json()

    res = client.post(
        f"/upgrades/{plan['plan_id']}/advance",
        json={"simulate_failure_agents": ["p7-a2"]},
    ).json()

    assert res["status"] == "ROLLED_BACK"
    assert client.get("/agents/p7-a1").json()["version"] == "1.0.0"
    assert client.get("/agents/p7-a2").json()["version"] == "1.0.0"


def test_orphaned_session_recovery_and_agent_recover(client):
    _register(client, "p7-fail")
    _register(client, "p7-healthy")

    job = client.post("/sessions/submit", json={"job_name": "critical-test"}).json()
    failing_id = job["agent_id"]
    healthy_id = "p7-healthy" if failing_id == "p7-fail" else "p7-fail"

    # Simulate agent going offline
    agent = agent_manager.get_agent(failing_id)
    agent.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=60)
    agent.health_status = AgentHealthStatus.OFFLINE

    rec = client.post("/recovery/reconcile").json()
    assert job["session_id"] in rec["requeued_orphaned_sessions"]

    updated_job = client.get(f"/sessions/{job['session_id']}").json()
    assert updated_job["status"] == "RUNNING"
    assert updated_job["agent_id"] == healthy_id
    assert updated_job["retry_count"] == 1

    # Recover the failed agent
    recovered = client.post(f"/agents/{failing_id}/recover").json()
    assert recovered["health_status"] == "HEALTHY"
    assert recovered["lifecycle_status"] == "READY"


# --- Phase 8: Monitoring Dashboard, Metrics & GitHub Actions ---


def test_prometheus_metrics_and_dashboard(client):
    _register(client, "p8-a1")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "ialm_agents_total 1.0" in metrics.text

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "Intelligent Agent Lifecycle Manager" in dash.text


def test_github_actions_webhook_and_runners(client, monkeypatch):
    _register(client, "gh-runner-1")
    secret = "super-secret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)

    queued_payload = {
        "action": "queued",
        "repository": {"full_name": "org/repo"},
        "workflow_job": {"id": 98765, "name": "ci-lint", "labels": ["self-hosted"]},
    }
    body = json.dumps(queued_payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    # Invalid signature rejected
    bad = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={"X-GitHub-Event": "workflow_job", "X-Hub-Signature-256": "sha256=bad"},
    )
    assert bad.status_code == 401

    # Valid queued webhook schedules job onto runner
    ok = client.post(
        "/integrations/github/webhook",
        content=body,
        headers={"X-GitHub-Event": "workflow_job", "X-Hub-Signature-256": sig},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "queued"
    session_id = ok.json()["session"]["session_id"]

    runners = client.get("/integrations/github/runners").json()["runners"]
    assert runners[0]["busy"] is True

    # Completed webhook finishes the session
    done_payload = {
        "action": "completed",
        "workflow_job": {"id": 98765, "name": "ci-lint", "conclusion": "success"},
    }
    done_body = json.dumps(done_payload).encode("utf-8")
    done_sig = "sha256=" + hmac.new(secret.encode(), done_body, hashlib.sha256).hexdigest()
    done = client.post(
        "/integrations/github/webhook",
        content=done_body,
        headers={"X-GitHub-Event": "workflow_job", "X-Hub-Signature-256": done_sig},
    )
    assert done.status_code == 200
    assert client.get(f"/sessions/{session_id}").json()["status"] == "COMPLETED"
