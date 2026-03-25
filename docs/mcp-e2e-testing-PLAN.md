# MCP Server E2E Testing Plan

End-to-end acceptance tests that prove the MCP server works as a real agent would use it: spin up an isolated environment, exercise all tools through the MCP protocol, verify mutations via the REST API, and tear down cleanly.

## Problem

We have 991 backend tests covering tool logic and 17 protocol-level tests that start the MCP server as a subprocess. But none of them prove:

1. The docker compose `mcp` service actually starts and serves tools correctly
2. An agent can follow the `available_actions` chain to complete a workflow
3. MCP tool calls actually mutate the database (verified independently via REST API)
4. The full stack (db → Django ORM → service layer → MCP tool → HTTP transport → auth) works together in a production-like deployment

The manual smoke tests in Phases 4 and 5 found 4 bugs that automated tests missed. All were deployment-level issues (DNS rebinding, double-import, async safety, SDK API changes).

## Solution

An isolated docker compose stack dedicated to E2E testing. A Python test runner connects via MCP HTTP client, executes scenarios that exercise all 9 tools, and verifies the results via the REST API (independent verification channel).

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Test Runner (pytest, runs on host or in container)  │
│                                                      │
│  ┌──────────────┐      ┌───────────────────┐        │
│  │ MCP Client   │      │ REST API Client   │        │
│  │ (httpx+MCP)  │      │ (httpx)           │        │
│  └──────┬───────┘      └─────────┬─────────┘        │
└─────────┼────────────────────────┼───────────────────┘
          │ MCP HTTP               │ REST HTTP
          │ :18002                 │ :18000
┌─────────┼────────────────────────┼───────────────────┐
│  docker-compose.e2e.yml                              │
│         │                        │                   │
│  ┌──────▼───────┐      ┌────────▼────────┐          │
│  │  mcp (:8002) │      │  api (:8000)    │          │
│  │  MCP server  │      │  Django REST    │          │
│  └──────┬───────┘      └────────┬────────┘          │
│         │                       │                    │
│  ┌──────▼───────────────────────▼────────┐          │
│  │  db (postgres, ephemeral volume)      │          │
│  └───────────────────────────────────────┘          │
└──────────────────────────────────────────────────────┘
```

### Dual verification

Every scenario verifies results through two independent channels:
1. **MCP response** — the tool returned `success: true` with expected data
2. **REST API query** — `GET /v1/tasks/{id}/` confirms the actual DB state

If MCP says "claimed" but REST shows "todo", the test fails. This catches response fabrication bugs.

### Available_actions-driven scenarios

Scenarios don't hardcode tool sequences. Instead, they follow the `available_actions` from each response to pick the next tool. This tests the guided workflow pattern:

```python
# Pseudocode
response = call_mcp("vtf_next_work", project_id=project_id)
assert "claim_and_start" in response["available_actions"]

response = call_mcp("vtf_claim_and_start", task_id=response["data"]["task"]["id"], agent_id=agent_id)
assert "vtf_report_progress" in response["available_actions"]
# ...
```

If we change the action chain in a tool, the scenario adapts. If the chain breaks, the test fails.

## Isolated Test Environment

### docker-compose.e2e.yml

Minimal stack: db + api + mcp. No celery, no redis (not needed for E2E tool tests). Different ports to avoid conflicts with dev stack.

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: vtf_e2e
      POSTGRES_USER: vtf
      POSTGRES_PASSWORD: vtftest
    tmpfs:
      - /var/lib/postgresql/data    # ephemeral — destroyed on down
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vtf -d vtf_e2e"]
      interval: 2s
      timeout: 2s
      retries: 10

  api:
    build: .
    command: python src/manage.py runserver 0.0.0.0:8000
    volumes:
      - ./src:/app/src
    ports:
      - "18000:8000"
    depends_on:
      db: { condition: service_healthy }
    environment:
      DJANGO_SETTINGS_MODULE: vtaskforge.settings.dev
      DATABASE_URL: postgres://vtf:vtftest@db:5432/vtf_e2e

  mcp:
    build: .
    command: python -c "from mcp_server.server import run_server; run_server()"
    volumes:
      - ./src:/app/src
    ports:
      - "18002:8002"
    depends_on:
      db: { condition: service_healthy }
    environment:
      VTF_MCP_TRANSPORT: http
      VTF_MCP_HOST: "0.0.0.0"
      VTF_MCP_PORT: "8002"
      DATABASE_URL: postgres://vtf:vtftest@db:5432/vtf_e2e
      DJANGO_SETTINGS_MODULE: vtaskforge.settings.dev
```

Key differences from dev stack:
- **tmpfs for DB** — ephemeral, no volume persistence, fast
- **Ports 18000/18002** — no conflict with dev stack (8000/8002)
- **Separate database** (`vtf_e2e`) — no risk to dev data
- **No celery/redis** — not needed for MCP tool testing

### Lifecycle

```bash
# Bring up
docker compose -f docker-compose.e2e.yml up -d --build --wait

# Run migrations + seed
docker compose -f docker-compose.e2e.yml exec api python src/manage.py migrate --run-syncdb
docker compose -f docker-compose.e2e.yml exec api python -c "exec(open('tests/e2e/seed.py').read())"

# Run tests
pytest tests/e2e/ -v --tb=short

# Tear down (destroys everything)
docker compose -f docker-compose.e2e.yml down -v
```

## Test Structure

```
tests/e2e/
  conftest.py                    # Fixtures: stack lifecycle, MCP client, REST client, seed data
  seed.py                        # Seed script: project, milestone, tasks, agent + tokens
  mcp_client.py                  # MCP HTTP client wrapper with available_actions helper
  rest_client.py                 # REST API client for independent verification
  test_executor_scenario.py      # Executor agent workflow
  test_supervisor_scenario.py    # Supervisor agent workflow
  test_lifecycle_scenario.py     # Full task lifecycle (create through delete)
  test_error_recovery.py         # Error paths: invalid actions, auth failures, bad state
```

### conftest.py

```python
import pytest
import subprocess
import time
import httpx

E2E_MCP_URL = "http://localhost:18002/mcp"
E2E_API_URL = "http://localhost:18000/v1"

@pytest.fixture(scope="session", autouse=True)
def e2e_stack():
    """Bring up the isolated E2E stack, seed it, yield, tear down."""
    subprocess.run(["docker", "compose", "-f", "docker-compose.e2e.yml", "up", "-d", "--build", "--wait"], check=True)
    # Run migrations
    subprocess.run(["docker", "compose", "-f", "docker-compose.e2e.yml", "exec", "api",
                     "python", "src/manage.py", "migrate", "--run-syncdb"], check=True)
    # Seed data
    subprocess.run(["docker", "compose", "-f", "docker-compose.e2e.yml", "exec", "api",
                     "python", "-c", "exec(open('/app/tests/e2e/seed.py').read())"], check=True)
    # Wait for MCP to be ready
    _wait_for_mcp()
    yield
    subprocess.run(["docker", "compose", "-f", "docker-compose.e2e.yml", "down", "-v"], check=True)

def _wait_for_mcp(timeout=30):
    """Poll MCP server until it responds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://localhost:18002/health", timeout=2)
            if r.status_code in (200, 404):  # server is up
                return
        except httpx.ConnectError:
            time.sleep(1)
    raise TimeoutError("MCP server did not start")
```

### seed.py

Creates known state that all scenarios reference:

```python
# Run inside the api container
import django
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from projects.models import Project
from workplans.models import Workplan, Milestone
from tasks.models import Task
from agents.models import Agent

# Admin user + token for REST API
user = User.objects.create_user("e2e-admin", password="e2e")
token = Token.objects.create(user=user)
print(f"API_TOKEN={token.key}")

# Project
project = Project.objects.create(id="e2e-project", name="E2E Test Project")

# Workplan + Milestone
wp = Workplan.objects.create(project=project, title="E2E Workplan")
ms = Milestone.objects.create(workplan=wp, name="E2E Milestone", position=0)

# Tasks in various states for scenarios
Task.objects.create(id="e2e-todo-1", title="Task ready for claiming", project=project,
                    milestone=ms, status="todo", spec="test: true")
Task.objects.create(id="e2e-todo-2", title="Second claimable task", project=project,
                    milestone=ms, status="todo")
Task.objects.create(id="e2e-blocked", title="Blocked task", project=project,
                    milestone=ms, status="blocked")
Task.objects.create(id="e2e-review", title="Task pending review", project=project,
                    milestone=ms, status="pending_completion_review",
                    needs_review_on_completion=True)
Task.objects.create(id="e2e-draft", title="Draft task", project=project,
                    milestone=ms, status="draft")

# Agent
agent = Agent.objects.create(id="e2e-executor", name="e2e-executor", status="online", tags=["executor"])

print(f"Seeded: project={project.id}, {Task.objects.count()} tasks, agent={agent.id}")
```

### Scenarios

#### test_executor_scenario.py — Executor agent workflow

```
Given: a project with todo tasks seeded
When: executor agent follows available_actions chain
Then: task moves todo → doing → done, verified via REST API
```

Steps:
1. `vtf_next_work(project_id)` → get recommended task
2. Assert `claim_and_start` in available_actions
3. `vtf_claim_and_start(task_id, agent_id)` → claim it
4. REST verify: `GET /v1/tasks/{id}/` → status=doing, claimed_by=agent_id
5. `vtf_report_progress(task_id, note)` → heartbeat
6. REST verify: claim_expires_at extended
7. `vtf_submit_work(task_id, completion_note)` → submit
8. REST verify: status=done or pending_completion_review

#### test_supervisor_scenario.py — Supervisor workflow

```
Given: a task in pending_completion_review
When: supervisor follows available_actions chain
Then: task approved and done, verified via REST API
```

Steps:
1. `vtf_board_overview(project_id)` → see pending_reviews count > 0
2. `vtf_search_tasks(status=pending_completion_review)` → find the task
3. `vtf_task_detail(task_id)` → see full context
4. `vtf_review_task(task_id, decision=approved)` → approve
5. REST verify: `GET /v1/tasks/{id}/` → status=done

#### test_lifecycle_scenario.py — Full lifecycle

```
Given: empty project
When: create → submit → claim → progress → submit → review → delete
Then: all state transitions verified via REST API at each step
```

This scenario creates its own task and moves it through every state, verifying at each step.

#### test_error_recovery.py — Error paths

```
Given: various invalid states
When: agent calls tools with bad inputs
Then: error responses are actionable, available_actions guide recovery
```

Tests:
- Claim a task that doesn't exist → error with `vtf_search_tasks` in available_actions
- Claim a task that's already claimed → error with `vtf_next_work` in available_actions
- Submit work on a task not in doing → error with correct guidance
- Review a task not in review status → error with correct guidance
- HTTP request without auth token → 401

## Task Breakdown

### P6.1 — E2E docker compose and conftest (no deps)
- Create `docker-compose.e2e.yml` (db + api + mcp, ephemeral, isolated ports)
- Create `tests/e2e/conftest.py` (stack lifecycle fixture)
- Create `tests/e2e/seed.py` (known test state)
- Create `tests/e2e/mcp_client.py` (MCP HTTP client wrapper)
- Create `tests/e2e/rest_client.py` (REST API client for verification)
- Verify: stack comes up, seeds, tests can connect to both MCP and REST

### P6.2 — Executor scenario (depends P6.1)
- Create `tests/e2e/test_executor_scenario.py`
- Exercises: next_work → claim_and_start → report_progress → submit_work
- Dual verification: MCP responses + REST API queries
- Follows available_actions chain (not hardcoded sequence)

### P6.3 — Supervisor scenario (depends P6.1)
- Create `tests/e2e/test_supervisor_scenario.py`
- Exercises: board_overview → search_tasks → task_detail → review_task
- Dual verification at each step

### P6.4 — Full lifecycle scenario (depends P6.1)
- Create `tests/e2e/test_lifecycle_scenario.py`
- Exercises: manage_task(create) → manage_task(submit) → claim → progress → submit_work → review → manage_task(delete)
- Verifies every state transition via REST API

### P6.5 — Error recovery scenario (depends P6.1)
- Create `tests/e2e/test_error_recovery.py`
- Tests all error paths: not found, wrong status, auth failure, invalid action
- Verifies available_actions in every error response guide to valid recovery

### P6.6 — CI runner script (depends P6.2-P6.5)
- Create `scripts/run-e2e.sh` — single command to bring up, test, tear down
- Exit code reflects test results (for CI integration)
- Handles cleanup even on test failure (trap)
- Add to docs/mcp-server-README.md

### G6 — Quality gate (depends P6.6)
- Run full backend test suite (must still pass)
- Run E2E tests via `scripts/run-e2e.sh`
- Verify isolated stack doesn't interfere with dev stack

## Not in scope

- **LLM-in-the-loop testing** — scenarios are scripted, not LLM-driven. An LLM smoke test could be a future periodic job but is too expensive/non-deterministic for CI.
- **Performance/load testing** — covered by existing `test_performance.py`
- **Frontend/web UI testing** — out of scope for MCP server
- **Multi-agent concurrent scenarios** — future work for vafi integration testing
