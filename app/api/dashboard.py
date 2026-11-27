from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

from app.core.agent_manager import agent_manager
from app.core.session_manager import session_manager
from app.core.upgrade_manager import upgrade_manager
from app.models.session import SessionStatus


router = APIRouter(tags=["Monitoring & Dashboard"])


@router.get("/metrics")
async def prometheus_metrics():
    registry = CollectorRegistry()
    summary = agent_manager.get_health_summary()
    sessions = session_manager.get_all_sessions()
    upgrades = upgrade_manager.get_all_plans()

    g_total = Gauge("ialm_agents_total", "Total registered agents", registry=registry)
    g_healthy = Gauge("ialm_agents_healthy", "Healthy agents", registry=registry)
    g_offline = Gauge("ialm_agents_offline", "Offline agents", registry=registry)
    g_avail = Gauge("ialm_agents_available", "Available agents", registry=registry)
    g_running = Gauge("ialm_sessions_running", "Running job sessions", registry=registry)
    g_queued = Gauge("ialm_sessions_queued", "Queued job sessions", registry=registry)
    g_upgrades = Gauge("ialm_upgrades_total", "Total rolling upgrade plans", registry=registry)

    g_total.set(summary["total_agents"])
    g_healthy.set(summary["healthy"])
    g_offline.set(summary["offline"])
    g_avail.set(summary["available"])
    g_running.set(sum(s.status == SessionStatus.RUNNING for s in sessions))
    g_queued.set(
        sum(s.status in (SessionStatus.QUEUED, SessionStatus.REQUEUED) for s in sessions)
    )
    g_upgrades.set(len(upgrades))

    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>IALM — Agent Lifecycle Dashboard</title>
  <style>
    :root { --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #f8fafc; --muted: #94a3b8; --green: #22c55e; --amber: #f59e0b; --red: #ef4444; --blue: #3b82f6; }
    * { box-sizing: border-box; font-family: Inter, system-ui, sans-serif; }
    body { margin: 0; background: var(--bg); color: var(--text); padding: 24px; }
    h1 { margin: 0 0 6px; font-size: 24px; }
    .sub { color: var(--muted); margin-bottom: 20px; font-size: 14px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
    .metric-label { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .metric-val { font-size: 28px; font-weight: 700; margin-top: 6px; }
    .section { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 20px; }
    h2 { margin: 0 0 12px; font-size: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 600; }
    .badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; display: inline-block; }
    .HEALTHY, .READY, .COMPLETED { background: rgba(34,197,94,0.18); color: var(--green); }
    .BUSY, .RUNNING, .IN_PROGRESS, .DRAINING, .UPGRADING { background: rgba(245,158,11,0.18); color: var(--amber); }
    .OFFLINE, .UNHEALTHY, .FAILED, .ROLLED_BACK { background: rgba(239,68,68,0.18); color: var(--red); }
    .QUEUED, .REQUEUED { background: rgba(59,130,246,0.18); color: var(--blue); }
  </style>
</head>
<body>
  <h1>Intelligent Agent Lifecycle Manager</h1>
  <div class="sub">Real-time CI/CD Agent Pool, Sessions, Rolling Upgrades &amp; Event Stream</div>
  <div class="grid" id="summary"></div>
  <div class="section"><h2>Agents</h2><table><thead><tr><th>ID</th><th>Name</th><th>Lifecycle</th><th>Health</th><th>Version</th><th>Active Jobs</th><th>Available</th></tr></thead><tbody id="agents"></tbody></table></div>
  <div class="section"><h2>Sessions</h2><table><thead><tr><th>Session ID</th><th>Job</th><th>Status</th><th>Agent</th><th>Retries</th></tr></thead><tbody id="sessions"></tbody></table></div>
  <div class="section"><h2>Recent Events</h2><table><thead><tr><th>Time</th><th>Type</th><th>Entity</th><th>Message</th></tr></thead><tbody id="events"></tbody></table></div>
  <script>
    async function refresh() {
      const [sum, ag, ses, ev] = await Promise.all([
        fetch('/agents/monitoring/summary').then(r => r.json()),
        fetch('/agents/').then(r => r.json()),
        fetch('/sessions/').then(r => r.json()),
        fetch('/agents/monitoring/events?limit=15').then(r => r.json()),
      ]);
      const cards = [
        ['Total Agents', sum.total_agents],
        ['Healthy', sum.healthy],
        ['Available', sum.available],
        ['Busy', sum.busy],
        ['Draining', sum.draining],
        ['Offline', sum.offline],
      ];
      document.getElementById('summary').innerHTML = cards.map(([k, v]) =>
        `<div class="card"><div class="metric-label">${k}</div><div class="metric-val">${v}</div></div>`
      ).join('');
      document.getElementById('agents').innerHTML = ag.map(a =>
        `<tr><td>${a.agent_id}</td><td>${a.agent_name}</td><td><span class="badge ${a.lifecycle_status}">${a.lifecycle_status}</span></td><td><span class="badge ${a.health_status}">${a.health_status}</span></td><td>${a.version}</td><td>${a.active_sessions}</td><td>${a.available_for_jobs}</td></tr>`
      ).join('') || '<tr><td colspan="7">No agents registered</td></tr>';
      document.getElementById('sessions').innerHTML = ses.map(s =>
        `<tr><td>${s.session_id}</td><td>${s.job_name}</td><td><span class="badge ${s.status}">${s.status}</span></td><td>${s.agent_id || '-'}</td><td>${s.retry_count}/${s.max_retries}</td></tr>`
      ).join('') || '<tr><td colspan="5">No sessions</td></tr>';
      document.getElementById('events').innerHTML = ev.slice().reverse().map(e =>
        `<tr><td>${new Date(e.timestamp).toLocaleTimeString()}</td><td>${e.event_type}</td><td>${e.agent_id}</td><td>${e.message}</td></tr>`
      ).join('') || '<tr><td colspan="4">No events</td></tr>';
    }
    refresh();
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)
