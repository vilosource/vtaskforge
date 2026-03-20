# vtaskforge

A distributed task execution system for LLM agents. Agents claim tasks from a pool, execute them, and report results. The system manages the full lifecycle — from draft through review, execution, and completion — with structured specs so any agent can pick up any task cold.

## How it works

```
Workplan → Phases → Tasks → Agents claim and execute
```

- **Workplans** group related work (e.g., "Auth system rewrite")
- **Phases** are ordered stages within a workplan
- **Tasks** are self-contained agent work packets with full implementation specs
- **Agents** claim tasks, execute them, and report results

Tasks carry everything an agent needs: description, acceptance criteria, implementation approach, file lists, constraints, references, and test commands. No filesystem access or prior context required.

## Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Server | Django 5.1 + DRF | REST API, task state machine, SSE events |
| Database | PostgreSQL 16 | Central store, atomic claims |
| Background | Celery + Redis | Claim expiry, periodic tasks |
| Web UI | React 18 + TypeScript | Kanban board, task detail, pipeline view |
| CLI | Python (Click) | `vtf` command-line tool |

## Quick start

```bash
# Start all services
docker compose up -d
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser

# Verify
curl http://localhost:8000/v1/health
```

The API is at `http://localhost:8000`. Django admin at `http://localhost:8000/admin/`.

See [docs/guides/quickstart-GUIDE.md](docs/guides/quickstart-GUIDE.md) for a full walkthrough.

## CLI (`vtf`)

```bash
# Install (development)
cd cli && pip install -e .

# Configure
vtf config set api_url http://localhost:8000

# Core workflow
vtf workplan list                          # List workplans
vtf import phases/phase1/ --workplan <id>  # Import phase with task specs
vtf task list --status todo                # Find claimable tasks
vtf task show <id>                         # View task details + spec
vtf task show <id> --json                  # Full JSON (for agents)
vtf task submit <id>                       # Move draft → todo
vtf task claim <id> --agent <agent-id>     # Claim a task
vtf task complete <id>                     # Mark done
vtf task fail <id>                         # Mark failed → needs_attention
```

## Web UI

The React SPA provides a Kanban board, full-page task detail view with parsed spec rendering, and a pipeline visualization.

```bash
cd web && npm install && npm run dev    # Development (port 3000, proxies API)
```

Or use the dogfood stack (built image, production settings):

```bash
docker compose -f docker-compose.dogfood.yml up -d    # Port 8001
```

## Running tests

```bash
# Backend (Django + DRF)
docker compose exec api pytest                    # All tests
docker compose exec api pytest tests/tasks/       # Specific app

# Frontend (React)
cd web && npx vitest run                          # All frontend tests

# CLI
cd cli && pytest tests/                           # CLI tests
```

## Task specs

Tasks store their full implementation contract in the `spec` field — a YAML document containing:

```yaml
description: |
  What to build and why.

files:
  create: [new_file.py]
  modify: [existing_file.py]
  affected: [related_file.py]

implementation:
  approach: |
    Step-by-step instructions with code examples.
  constraints:
    - Hard rules the implementation must follow
  references:
    - files/to/read/first.py

acceptance_criteria:
  - "What success looks like"

test_command:
  unit: "pytest tests/specific_test.py"
```

Agents read the spec from the API (`vtf task show <id> --json`) and have everything they need to execute.

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/design/vtaskforge-DESIGN.md](docs/design/vtaskforge-DESIGN.md) | Core design: concepts, entity shapes, decisions |
| [docs/design/api-surface-DESIGN.md](docs/design/api-surface-DESIGN.md) | REST API endpoints, SSE events, error model |
| [docs/design/actor-model-DESIGN.md](docs/design/actor-model-DESIGN.md) | Agent roles, interaction patterns |
| [docs/guides/quickstart-GUIDE.md](docs/guides/quickstart-GUIDE.md) | Zero to running in 5 minutes |
| [docs/guides/phase-process-GUIDE.md](docs/guides/phase-process-GUIDE.md) | How to plan and execute phases |
| [docs/guides/task-breakdown-GUIDE.md](docs/guides/task-breakdown-GUIDE.md) | Decomposing work into agent tasks |
| [WORKPLAN.md](WORKPLAN.md) | Phase index and status |

## Claude Code agents

Four agents automate the development workflow:

| Agent | Role |
|-------|------|
| `vtf-supervisor` | Orchestrates phase execution, dispatches executors, runs verification gates |
| `vtf-executor` | Implements a single task from its spec, runs tests, commits |
| `vtf-judge` | Reviews code changes for design compliance and architectural issues |
| `vtf-blackbox-tester` | End-to-end API testing via HTTP requests only |

## License

Private — not yet open source.
