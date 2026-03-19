# vtaskforge — Implementation Plan

Status: Planning (2026-03-19)

## Phase 0 — Project Setup & Dev Environment

**Goal:** A Django project skeleton that boots in Docker, responds to a health endpoint, and has Celery connected. No business logic — just the foundation.

### Project Structure

```
vtaskforge/
├── docker-compose.yml              # Dev environment
├── docker-compose.prod.yml         # Production (future)
├── Dockerfile                      # Django app image
├── requirements/
│   ├── base.txt                    # Django, DRF, psycopg2, celery, redis
│   ├── dev.txt                     # pytest, pytest-django, factory-boy, flake8
│   └── prod.txt                    # gunicorn, whitenoise
├── src/
│   ├── manage.py
│   ├── vtaskforge/
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Shared settings
│   │   │   ├── dev.py              # Dev overrides (DEBUG=True, etc.)
│   │   │   └── prod.py             # Prod overrides
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── celery.py               # Celery app configuration
│   ├── core/                       # Shared: base models, utils, mixins
│   ├── initiatives/                # Initiative + Phase models, serializers, views
│   ├── tasks/                      # Task models, state machine, serializers, views
│   ├── links/                      # Link system models, serializers, views
│   ├── reviews/                    # Review system models, serializers, views
│   ├── events/                     # Task events + SSE stream
│   └── agents/                     # Agent registration, auth tokens
├── tests/
│   ├── conftest.py
│   ├── test_health.py              # Phase 0 smoke test
│   └── ...
├── docs/                           # Design docs (already exists)
└── CLAUDE.md                       # Dev commands and project context
```

### Docker Dev Setup

**docker-compose.yml:**

```yaml
services:
  api:
    build: .
    command: python src/manage.py runserver 0.0.0.0:8000
    volumes:
      - ./src:/app/src              # Mount source — hot reload, no rebuild
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    environment:
      - DJANGO_SETTINGS_MODULE=vtaskforge.settings.dev
      - DATABASE_URL=postgres://vtf:vtfdev@db:5432/vtaskforge
      - CELERY_BROKER_URL=redis://redis:6379/0

  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=vtaskforge
      - POSTGRES_USER=vtf
      - POSTGRES_PASSWORD=vtfdev
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vtf -d vtaskforge"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  celery:
    build: .
    command: celery -A vtaskforge worker -l info
    volumes:
      - ./src:/app/src
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    environment:
      - DJANGO_SETTINGS_MODULE=vtaskforge.settings.dev
      - DATABASE_URL=postgres://vtf:vtfdev@db:5432/vtaskforge
      - CELERY_BROKER_URL=redis://redis:6379/0

  celery-beat:
    build: .
    command: celery -A vtaskforge beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - ./src:/app/src
    depends_on:
      redis:
        condition: service_started
    environment:
      - DJANGO_SETTINGS_MODULE=vtaskforge.settings.dev
      - CELERY_BROKER_URL=redis://redis:6379/0

volumes:
  pgdata:
```

**Dockerfile (dev-optimized):**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Python deps — separate layer, only rebuilds when requirements change
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/dev.txt

# Source — mounted over this in dev, used in prod
COPY src/ src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
```

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Python version | 3.12 | Latest stable, performance improvements |
| Postgres version | 16 | Latest stable, needed for array containment (`<@`) in claims |
| Redis | 7-alpine | Celery broker, lightweight |
| Settings split | base/dev/prod | Standard Django pattern, env-specific config |
| Source mount | `./src:/app/src` | Hot reload in dev, no rebuild on code changes |
| Same image for all services | api, celery, celery-beat | Different commands, same codebase |
| `DATABASE_URL` env var | dj-database-url | 12-factor, same pattern in dev and prod |

### Django Apps

| App | Purpose | Phase 0 scope |
|---|---|---|
| `core` | Base models (NanoID mixin, timestamp mixin), shared utils | Create app, base model mixins |
| `initiatives` | Initiative + Phase models, views | Create app only, no models yet |
| `tasks` | Task models, state machine, views | Create app only, no models yet |
| `links` | Link system | Create app only, no models yet |
| `reviews` | Review system | Create app only, no models yet |
| `events` | Task events + SSE | Create app only, no models yet |
| `agents` | Agent registration, tokens | Create app only, no models yet |

### Completion Checklist

Phase 0 is NOT complete until every item below is verified. No exceptions.

#### Infrastructure
- [ ] `docker compose up -d` starts all 5 services (api, db, redis, celery, celery-beat) without errors
- [ ] `docker compose ps` shows all 5 services in "running" state
- [ ] `docker compose down && docker compose up -d` (cold start) works without manual intervention
- [ ] Postgres container passes healthcheck (`pg_isready`)
- [ ] Source code changes in `./src/` are reflected immediately in the running api container without rebuild (hot reload verified)
- [ ] Rebuilding image (`docker compose build`) is only required when `requirements/*.txt` files change

#### API Server
- [ ] `GET /v1/health` returns `200 OK` with JSON body containing `db: "ok"` and `redis: "ok"`
- [ ] `GET /v1/health` returns appropriate error status when DB is down
- [ ] `GET /v1/health` returns appropriate error status when Redis is down
- [ ] Django admin is accessible at `/admin/` and login works with a superuser
- [ ] API returns `application/json` content type on all responses
- [ ] API returns proper 404 JSON response for unknown routes (not Django HTML debug page)

#### Django Apps
- [ ] All 7 apps created: `core`, `initiatives`, `tasks`, `links`, `reviews`, `events`, `agents`
- [ ] All 7 apps registered in `INSTALLED_APPS`
- [ ] `core` app contains `NanoIDMixin` (or equivalent) for generating nanoid primary keys
- [ ] `core` app contains `TimestampMixin` with `created_at` and `updated_at` fields
- [ ] `python manage.py check` passes with no warnings
- [ ] `python manage.py migrate` runs without errors (even if no custom migrations yet)

#### Settings
- [ ] Settings split into `base.py`, `dev.py`, `prod.py`
- [ ] `dev.py` has `DEBUG=True`, permissive CORS, console email backend
- [ ] `prod.py` has `DEBUG=False`, restricted ALLOWED_HOSTS (values TBD)
- [ ] Database configured via `DATABASE_URL` environment variable
- [ ] Celery broker configured via `CELERY_BROKER_URL` environment variable
- [ ] Secret key sourced from environment variable (not hardcoded) in `base.py`

#### Celery
- [ ] Celery worker connects to Redis and shows "ready" in logs
- [ ] Celery beat starts without errors
- [ ] A test task (e.g., `add(2, 3)`) can be dispatched and returns the correct result
- [ ] Test task execution is visible in celery worker logs

#### Testing
- [ ] `pytest` runs inside the container: `docker compose exec api pytest`
- [ ] Health endpoint smoke test passes (test `GET /v1/health` returns 200)
- [ ] Test uses `pytest-django` with a test database (not the dev database)
- [ ] At least one test per: health endpoint OK, health endpoint DB failure, celery test task
- [ ] All tests pass on a clean `docker compose up` (no manual setup steps)

#### Documentation
- [ ] `CLAUDE.md` exists in project root with:
  - [ ] Project purpose (one paragraph)
  - [ ] Dev setup instructions (`docker compose up`)
  - [ ] How to run tests
  - [ ] How to run Django management commands
  - [ ] How to rebuild after requirements change
  - [ ] Environment variables reference
- [ ] `docs/implementation-PLAN.md` Phase 0 checklist is fully checked off

#### Code Quality
- [ ] No hardcoded secrets in any committed file
- [ ] `.gitignore` covers: `__pycache__`, `*.pyc`, `.env`, `db.sqlite3`, `*.egg-info`, `.pytest_cache`
- [ ] No Django debug toolbar or development-only middleware leaking into `base.py`
- [ ] All Python files pass `flake8` (or equivalent linter) with zero errors

### Dev Commands (for CLAUDE.md)

```bash
# Start dev environment
docker compose up -d

# Run tests
docker compose exec api pytest

# Django management commands
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
docker compose exec api python src/manage.py shell

# View logs
docker compose logs -f api
docker compose logs -f celery

# Rebuild (only needed when requirements change)
docker compose build

# Stop
docker compose down
```

---

## Phase 1 — Core Models & Basic CRUD

*To be designed after Phase 0 is complete.*

Likely scope: Initiative, Phase, Task, Link models + migrations + basic DRF serializers and viewsets. State machine enforcement on Task transitions.

## Phase 2+

*To be planned.*
