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

### Deliverables

Phase 0 is complete when:

1. `docker compose up` boots all services (api, db, redis, celery, celery-beat)
2. `GET /v1/health` returns `200 OK` with DB and Redis connection status
3. Django admin is accessible at `/admin/`
4. All Django apps are created and registered in settings
5. Celery worker connects to Redis and processes a test task
6. `pytest` runs with a passing smoke test (health endpoint)
7. CLAUDE.md documents dev commands

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
