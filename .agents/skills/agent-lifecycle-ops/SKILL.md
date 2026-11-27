---
name: agent-lifecycle-ops
description: Operate the Intelligent Agent Lifecycle Manager API for agent registration, heartbeats, session scheduling, graceful draining, rolling upgrades, failure recovery, and GitHub Actions webhooks.
---

# Agent Lifecycle Operations

Use this skill when running, testing, or demonstrating lifecycle workflows against the IALM FastAPI service.

## 1. Start the Server
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

## 2. Core Endpoints by Phase
- **Agents & Health**: `POST /agents/register`, `GET /agents/`, `POST /agents/{id}/heartbeat`, `GET /agents/monitoring/health`, `GET /agents/monitoring/summary`, `GET /agents/monitoring/available`, `GET /agents/monitoring/events`
- **Sessions**: `POST /sessions/submit`, `POST /sessions/schedule`, `GET /sessions/`, `POST /sessions/{id}/complete`, `POST /sessions/{id}/cancel`
- **Draining**: `POST /agents/{id}/drain`, `POST /agents/{id}/undrain`
- **Upgrades & Rollback**: `POST /agents/{id}/upgrade`, `POST /upgrades/rolling`, `POST /upgrades/{plan_id}/advance`, `POST /upgrades/{plan_id}/rollback`
- **Recovery**: `POST /agents/{id}/recover`, `POST /recovery/reconcile`
- **Observability & GitHub Actions**: `GET /metrics`, `GET /dashboard`, `POST /integrations/github/webhook`, `GET /integrations/github/runners`
