# Intelligent Agent Lifecycle Manager (IALM)

## Project Overview
FastAPI-based platform for automated CI/CD agent lifecycle management, heartbeat & health monitoring, job session scheduling, graceful draining, automated & rolling upgrades, failure recovery/rollback, Prometheus metrics, live dashboard, and GitHub Actions runner integration.

## Architecture
- `app/main.py` — FastAPI app initialization, `config/config.yaml` loading, background `HealthMonitor` lifespan, and router registration.
- `app/models/` — Pydantic models:
  - `agent.py` (`Agent`, `AgentLifecycleStatus`, `AgentHealthStatus`)
  - `session.py` (`JobSession`, `SessionStatus`)
  - `upgrade.py` (`UpgradePlan`, `UpgradeStatus`)
- `app/core/` — Core orchestration singletons:
  - `agent_manager.py` (`agent_manager`) — registration, heartbeats, health evaluation, availability, graceful draining (`start_drain`, `undrain_agent`, `reconcile_draining`)
  - `health_monitor.py` (`HealthMonitor`) — async background health check and pool reconciliation loop
  - `session_manager.py` (`session_manager`) — job queueing, scheduling onto available agents, completion, cancellation, timeouts, requeueing
  - `upgrade_manager.py` (`upgrade_manager`) — single-agent upgrades, batched rolling upgrades, auto/manual rollback
  - `recovery_manager.py` (`recovery_manager`) — orphaned session recovery, agent recovery with max attempts, pool reconciliation
- `app/monitoring/event_logger.py` — in-memory ring-buffer `event_logger` for lifecycle audit events
- `app/integrations/github_actions.py` — `workflow_job` webhook handler (with optional `GITHUB_WEBHOOK_SECRET` HMAC-SHA256 verification) and runner status mapping
- `app/api/` — FastAPI routers (`agents.py`, `sessions.py`, `upgrades.py`, `integrations.py`, `dashboard.py`)

## Conventions & Rules
- **Python Environment**: Always use `.\venv\Scripts\python.exe` on Windows.
- **FastAPI Route Ordering**: In `app/api/agents.py`, keep static `/agents/monitoring/*` routes registered *before* parameterized `/{agent_id}` and `/{agent_id}/health` routes so `/agents/monitoring/health` is not matched as `agent_id="monitoring"`.
- **Verification**: After any code change, run:
  ```powershell
  .\venv\Scripts\python.exe -m pytest -v
  ruff check app
  ```
