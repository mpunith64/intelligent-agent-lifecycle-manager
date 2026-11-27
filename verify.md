# Intelligent Agent Lifecycle Manager — Verification & Usage Guide

## 0. Environment Setup & Start Server

```powershell
# 1. Allow local PowerShell script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 2. (First time only) Create venv and install dependencies
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Activate venv (if not already active) and start FastAPI server
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

- **Swagger UI**: http://127.0.0.1:8000/docs
- **Live Dashboard**: http://127.0.0.1:8000/dashboard
- **Prometheus Metrics**: http://127.0.0.1:8000/metrics

---

## Phase 1 & 2: Register Agents, Heartbeats & Health Monitoring

Register sample agents (`POST /agents/register`):

| Agent ID | Agent Name |
|---|---|
| `agent-001` | `build-agent-01` |
| `agent-002` | `build-agent-02` |
| `agent-003` | `build-agent-03` |

```powershell
$base = "http://127.0.0.1:8000"

# Register 3 agents
Invoke-RestMethod -Method POST "$base/agents/register" -ContentType "application/json" -Body '{"agent_id":"agent-001","agent_name":"build-agent-01"}'
Invoke-RestMethod -Method POST "$base/agents/register" -ContentType "application/json" -Body '{"agent_id":"agent-002","agent_name":"build-agent-02"}'
Invoke-RestMethod -Method POST "$base/agents/register" -ContentType "application/json" -Body '{"agent_id":"agent-003","agent_name":"build-agent-03"}'

# List agents & send heartbeat
Invoke-RestMethod "$base/agents/"
Invoke-RestMethod -Method POST "$base/agents/agent-001/heartbeat"

# Health checks, summary, available pool, and event history
Invoke-RestMethod "$base/agents/monitoring/health"
Invoke-RestMethod "$base/agents/monitoring/summary"
Invoke-RestMethod "$base/agents/monitoring/available"
Invoke-RestMethod "$base/agents/monitoring/events?limit=20"
```

---

## Phase 3: Session Management & Job Scheduling

```powershell
# Submit a CI/CD job (auto-schedules onto an available READY agent)
$session = Invoke-RestMethod -Method POST "$base/sessions/submit" -ContentType "application/json" -Body '{"job_name":"build-and-test"}'
$session

# List sessions
Invoke-RestMethod "$base/sessions/"

# Complete the session (frees the agent back to READY)
Invoke-RestMethod -Method POST "$base/sessions/$($session.session_id)/complete" -ContentType "application/json" -Body '{"exit_code":0}'
```

---

## Phase 4: Graceful Agent Draining

```powershell
# Drain an agent (stops accepting new jobs; lets in-flight jobs finish)
Invoke-RestMethod -Method POST "$base/agents/agent-001/drain?reason=maintenance"

# Return drained agent to active pool
Invoke-RestMethod -Method POST "$base/agents/agent-001/undrain"
```

---

## Phase 5: Automated Single-Agent Upgrade

```powershell
# Upgrade an idle agent (if busy, it automatically enters DRAINING first)
Invoke-RestMethod -Method POST "$base/agents/agent-001/upgrade?target_version=2.0.0"
```

---

## Phase 6: Rolling Agent Upgrades

```powershell
# Create a rolling upgrade plan across remaining agents (batch_size=1, max_unavailable=1)
$plan = Invoke-RestMethod -Method POST "$base/upgrades/rolling" -ContentType "application/json" -Body '{"target_version":"2.0.0","batch_size":1,"max_unavailable":1,"auto_rollback":true}'
$plan

# Advance the rolling upgrade batch-by-batch until status == COMPLETED
Invoke-RestMethod -Method POST "$base/upgrades/$($plan.plan_id)/advance"
Invoke-RestMethod "$base/upgrades/$($plan.plan_id)"
```

---

## Phase 7: Failure Recovery & Rollback

```powershell
# Reconcile pool (requeue orphaned sessions from offline/unhealthy agents & check drain timeouts)
Invoke-RestMethod -Method POST "$base/recovery/reconcile"

# Recover an offline/unhealthy agent
Invoke-RestMethod -Method POST "$base/agents/agent-001/recover"

# Manually roll back a rolling upgrade plan
Invoke-RestMethod -Method POST "$base/upgrades/$($plan.plan_id)/rollback" -ContentType "application/json" -Body '{"reason":"manual verification rollback"}'
```

---

## Phase 8: Monitoring Dashboard & GitHub Actions Integration

```powershell
# View Prometheus metrics
Invoke-RestMethod "$base/metrics"

# View GitHub Actions runner mapping
Invoke-RestMethod "$base/integrations/github/runners"

# Simulate a GitHub Actions workflow_job webhook (queued -> completed)
Invoke-RestMethod -Method POST "$base/integrations/github/webhook" `
  -Headers @{"X-GitHub-Event"="workflow_job"} `
  -ContentType "application/json" `
  -Body '{"action":"queued","repository":{"full_name":"org/repo"},"workflow_job":{"id":1001,"name":"ci-build","labels":["self-hosted"]}}'

Invoke-RestMethod -Method POST "$base/integrations/github/webhook" `
  -Headers @{"X-GitHub-Event"="workflow_job"} `
  -ContentType "application/json" `
  -Body '{"action":"completed","workflow_job":{"id":1001,"name":"ci-build","conclusion":"success"}}'
```

---

## Automated Tests & Linting

```powershell
.\venv\Scripts\python.exe -m pytest -v
ruff check app
```
