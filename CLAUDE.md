# CLAUDE.md

## Project Purpose

vtaskforge (vtf) is a distributed task execution system for LLM agents. Django/DRF API server backed by Postgres, with Celery for background processing and a React SPA web UI. See `docs/design/vtaskforge-DESIGN.md` for full design, `WORKPLAN.md` for milestone index.

## Dev Setup

### Backend (API + DB + Celery)

```bash
docker compose up -d
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
```

Services: api (port 8000), db (Postgres, host port 5436), redis (6379), celery, celery-beat.

### Frontend (React SPA)

```bash
cd web && npm install && npm run dev    # Vite dev server on port 3000, proxies /v1 to 8000
```

### CLI

```bash
cd cli && pip install -e .
vtf config set api_url http://localhost:8000
vtf health                                       # Verify connectivity
```

### Dogfood (production-like instance)

```bash
docker compose -f docker-compose.dogfood.yml build dogfood-api
docker compose -f docker-compose.dogfood.yml up -d
# Web UI at http://localhost:8001, login: admin/admin
# Separate DB, built image (no volume mounts), gunicorn + gevent
```

After code changes, rebuild and restart: `docker compose -f docker-compose.dogfood.yml build dogfood-api && docker compose -f docker-compose.dogfood.yml up -d dogfood-api`

Apply migrations on dogfood: `docker compose -f docker-compose.dogfood.yml exec dogfood-api python src/manage.py migrate`

## Running Tests

```bash
# Backend — all tests
docker compose exec api pytest

# Backend — specific app
docker compose exec api pytest tests/tasks/
docker compose exec api pytest tests/core/
docker compose exec api pytest tests/events/

# Frontend
cd web && npx vitest run

# CLI
cd cli && pytest tests/
```

Test config in `pyproject.toml`. Uses `pytest-django` with a separate test DB. Celery tests run in eager mode.

## vtf CLI Reference

```bash
# Configuration
vtf config set api_url http://localhost:8000     # Point at dev
vtf config set api_url http://localhost:8001     # Point at dogfood
vtf health                                       # Check API connectivity

# Workplans
vtf workplan list
vtf workplan create --name "My Project"
vtf workplan show <id>
vtf workplan stats <id>

# Milestones
vtf milestone list --workplan <id>

# Importing milestones (from YAML specs)
vtf import milestones/milestone6/                        # Creates new workplan
vtf import milestones/milestone7/ --workplan <id>        # Adds milestone to existing workplan
vtf import milestones/milestone6/ --dry-run              # Preview without creating

# Tasks
vtf task list                                    # All tasks
vtf task list --status todo                      # Claimable tasks
vtf task show <id>                               # Human-readable detail
vtf task show <id> --json                        # Full JSON (for agents — includes spec)
vtf task submit <id>                             # draft → todo
vtf task claim <id> --agent <agent-id> --tags executor
vtf task complete <id>                           # doing → done
vtf task fail <id>                               # doing → needs_attention

# Agents
vtf agent register --name "my-agent" --tags executor,sonnet
vtf agent list
```

## Task Spec Structure

Tasks store their full implementation contract in the `spec` field (YAML text). Key fields within the spec:

- `implementation.approach` — step-by-step instructions (often with code examples)
- `implementation.constraints` — hard rules
- `implementation.references` — files to read before implementing
- `files.create/modify/affected` — file scope boundaries
- `acceptance_criteria` — what success looks like
- `test_command` — verification commands (e.g., `{"unit": "pytest tests/"}`)
- `agent_model` — which LLM model to use (sonnet, opus)
- `judge` — whether judge review is required after completion
- `isolation` — sequential or parallel execution

## Milestone Import Workflow

```
1. Write YAML specs in milestones/<name>/tasks/*.yaml
2. Write dag.yaml for dependencies
3. vtf import milestones/<name>/ --workplan <id>
4. Tasks appear on the Kanban board with full specs
5. Submit tasks (draft → todo), claim, execute, complete
```

## Django Management Commands

```bash
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
docker compose exec api python src/manage.py shell
docker compose exec api python src/manage.py makemigrations <app>
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `vtaskforge.settings.dev` | Settings module |
| `DATABASE_URL` | `postgres://vtf:vtfdev@db:5432/vtaskforge` | Postgres connection |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis broker URL |
| `SECRET_KEY` | `dev-insecure-key-change-in-prod` | Django secret key |
| `ALLOWED_HOSTS` | `*` (dev) | Comma-separated hostnames (prod) |

Postgres mapped to host port **5436** (not 5432) to avoid conflicts.

## Project Structure

```
src/
  vtaskforge/          # Django project config (settings, urls, celery, wsgi)
  core/                # Base mixins (NanoIDMixin, TimestampMixin), health, bulk import
  workplans/           # Workplan + Milestone models, stats
  tasks/               # Task model, state machine, claiming, lifecycle actions
  links/               # Universal link system (depends_on, blocks, area, doc, etc.)
  reviews/             # Review decisions at review gates
  events/              # Task events (audit log) + SSE streaming
  agents/              # Agent registration, tokens
tests/                 # pytest-django test suite, organized by app
cli/vtf/               # CLI tool (Click), commands for workplan/task/agent/import
web/                   # React 18 SPA (Vite, TypeScript, TanStack Query, React Router)
  src/pages/           # WorkplanList, WorkplanDetail, BoardView, TaskPage
  src/components/      # TaskDetail modal, TaskCard, DependencyChain, SpecSection, etc.
  src/api/             # API hooks (useTaskDetail, useMilestones, etc.)
  src/utils/           # parseSpec (YAML → structured data)
milestones/            # Milestone spec directories (YAML task specs, dag.yaml)
docs/
  design/              # Design docs, analysis, session handoff
  guides/              # Process guides, task breakdown, quickstart
  proposals/           # Agent pool manager, scrum master agent
  references/          # GitLab pipeline analogy
requirements/          # Python deps (base.txt, dev.txt, prod.txt)
```

## Key Endpoints

- `GET /v1/health` — health check
- `GET /v1/workplans/` — list workplans
- `GET /v1/tasks/:id/?expand=links,reviews,events` — full task detail
- `GET /v1/events/stream/?workplan=<id>` — SSE event stream
- `POST /v1/bulk/import` — bulk create workplan/phases/tasks
- `/admin/` — Django admin

## Claude Code Agents

Four agents in `~/.claude/agents/`:

| Agent | Model | Purpose |
|-------|-------|---------|
| `vtf-supervisor` | opus | Orchestrates milestones, dispatches executors, runs verification gates |
| `vtf-executor` | sonnet | Implements a single task from spec, tests, commits |
| `vtf-judge` | opus | Code review for design compliance |
| `vtf-blackbox-tester` | sonnet | End-to-end API testing via HTTP |

The supervisor reads task specs from the API (`vtf task show <id> --json`), dispatches executors with the spec content, and runs test gates.

## Rebuilding

Only needed when `requirements/*.txt` or `web/package.json` change:

```bash
docker compose build                    # Dev
docker compose -f docker-compose.dogfood.yml build dogfood-api  # Dogfood
```

Source changes are auto-reloaded in dev (volume mount + Django reloader). Dogfood requires rebuild.

## Viewing Logs

```bash
docker compose logs -f api
docker compose logs -f celery
docker compose -f docker-compose.dogfood.yml logs -f dogfood-api
```
