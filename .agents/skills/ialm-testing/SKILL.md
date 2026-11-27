---
name: ialm-testing
description: Run unit/integration tests, lint checks, and FastAPI TestClient verification for the Intelligent Agent Lifecycle Manager repository.
---

# IALM Testing & Verification

1. Run the full `pytest` suite using the project virtual environment:
   ```powershell
   .\venv\Scripts\python.exe -m pytest -v
   ```
2. Run `ruff` linter checks:
   ```powershell
   ruff check app tests
   ```
3. Ensure test isolation: tests that use `agent_manager`, `session_manager`, `upgrade_manager`, `github_actions`, or `event_logger` should clear their in-memory stores between tests (see `clean_state` fixture in `tests/test_lifecycle_phases.py`).
