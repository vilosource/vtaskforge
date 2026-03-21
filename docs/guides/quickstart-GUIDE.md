# Quickstart Guide

Get vtaskforge running and create your first workplan in 5 minutes.

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for web UI development)
- Python 3.12+ (for CLI)

## 1. Start the services

```bash
git clone <repo-url> && cd vtaskforge
docker compose up -d
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
```

Verify: `curl http://localhost:8000/v1/health` should return `{"status": "ok"}`.

## 2. Install the CLI

```bash
cd cli && pip install -e .
vtf config set api_url http://localhost:8000
vtf health
```

## 3. Create a workplan with milestones and tasks

### Option A: Write YAML specs and import

Create a milestone directory:

```
my-project/
  MILESTONE.md          # Milestone description (optional)
  dag.yaml          # Task dependencies
  tasks/
    1.1-first-task.yaml
    1.2-second-task.yaml
```

**dag.yaml:**
```yaml
tasks:
  - id: "1.1"
    name: "First task"
    depends_on: []
  - id: "1.2"
    name: "Second task"
    depends_on: ["1.1"]
```

**tasks/1.1-first-task.yaml:**
```yaml
id: "1.1"
name: "First task"
depends_on: []
agent_model: sonnet
isolation: sequential
judge: false

description: |
  What to build and why.

files:
  create:
    - src/new_file.py
  modify:
    - src/existing_file.py
  affected: []

implementation:
  approach: |
    Step 1: Read existing_file.py to understand the current pattern.
    Step 2: Create new_file.py following the same pattern.
    Step 3: Run tests.
  constraints:
    - Do not change the public API
  references:
    - src/existing_file.py

acceptance_criteria:
  - "new_file.py exists and follows the existing pattern"
  - "All tests pass"

test_command:
  unit: "pytest tests/"
```

Import:
```bash
vtf import my-project/                          # Creates a new workplan
# or
vtf import my-project/ --workplan <existing-id>  # Adds milestone to existing workplan
```

### Option B: Create via CLI

```bash
vtf workplan create --name "My Project"
# Then use the API or web UI to add milestones and tasks
```

## 4. Register an agent and execute tasks

```bash
# Register
vtf agent register --name "my-executor" --tags executor,sonnet

# Find work
vtf task list --status todo

# View a task's full spec
vtf task show <task-id>
vtf task show <task-id> --json    # Full JSON with spec field

# Execute the workflow
vtf task submit <task-id>          # draft → todo (make it available)
vtf task claim <task-id> --agent <agent-id> --tags executor
# ... do the work ...
vtf task complete <task-id>        # Mark done
```

## 5. Use the web UI

### Development mode
```bash
cd web && npm install && npm run dev
# Open http://localhost:3000
```

### Dogfood mode (production-like)
```bash
docker compose -f docker-compose.dogfood.yml build dogfood-api
docker compose -f docker-compose.dogfood.yml up -d
# Open http://localhost:8001, login: admin/admin
```

The web UI provides:
- **Workplan list** with milestone counts and progress bars
- **Milestone detail** with list view and pipeline visualization
- **Kanban board** per milestone with task cards
- **Task detail modal** (quick glance) with "Open full view" link
- **Full page task view** at `/tasks/:id` — two-column layout with parsed spec, dependency chain, notes, event timeline

## 6. Using Claude Code agents

The vtf-supervisor agent orchestrates execution:

```
"Run the supervisor for Milestone 1"
```

It will:
1. Find todo tasks via `vtf task list --status todo`
2. Read each task's spec via `vtf task show <id> --json`
3. Dispatch an executor agent (Sonnet) with the spec
4. Run verification gates (task-specific tests + full test suite)
5. Optionally dispatch a judge agent for code review
6. Mark tasks complete or failed

You can also run individual tasks manually — the supervisor is optional.

## Task lifecycle

```
draft → todo → doing → done
              ↘ needs_attention (agent gave up)
              ↘ blocked (external dependency)
```

Full state machine with review gates: see `docs/design/vtaskforge-DESIGN.md`.

## Next steps

- Read the [main design doc](../design/vtaskforge-DESIGN.md) for concepts and decisions
- Read the [API surface doc](../design/api-surface-DESIGN.md) for all endpoints
- Read the [milestone process guide](milestone-process-GUIDE.md) for how to plan milestones
- Read the [task breakdown guide](task-breakdown-GUIDE.md) for writing good task specs
