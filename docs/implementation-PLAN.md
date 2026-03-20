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
│   ├── workplans/                  # Workplan + Phase models, serializers, views
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
| `workplans` | Workplan + Phase models, views | Create app only, no models yet |
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
- [ ] All 7 apps created: `core`, `workplans`, `tasks`, `links`, `reviews`, `events`, `agents`
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

### Task Breakdown

Phase 0 structured as a vtaskforge workplan — tasks with dependencies forming a DAG.

#### Task 0.1: Project scaffolding & .gitignore

Create the full directory structure and `.gitignore`.

**Files to create:**
```
.gitignore
requirements/           (empty dir)
src/
src/manage.py           (placeholder — replaced in task 0.5)
src/vtaskforge/
src/vtaskforge/__init__.py
src/vtaskforge/settings/
src/vtaskforge/settings/__init__.py
src/core/__init__.py
src/core/apps.py        (placeholder AppConfig)
src/workplans/__init__.py
src/workplans/apps.py
src/tasks/__init__.py
src/tasks/apps.py
src/links/__init__.py
src/links/apps.py
src/reviews/__init__.py
src/reviews/apps.py
src/events/__init__.py
src/events/apps.py
src/agents/__init__.py
src/agents/apps.py
tests/__init__.py
```

**.gitignore must include:**
```
__pycache__/
*.pyc
*.pyo
.env
db.sqlite3
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
*.log
.DS_Store
```

- **Acceptance criteria:**
  - All directories and files above exist in the repo
  - `.gitignore` covers all listed patterns
  - `find src -name "*.py" | wc -l` shows the expected file count
- **Depends on:** nothing

---

#### Task 0.2: Requirements files

Create `requirements/base.txt`, `dev.txt`, `prod.txt`.

**base.txt — core dependencies:**
```
Django>=5.1,<5.2
djangorestframework>=3.15,<4.0
django-cors-headers>=4.3,<5.0
dj-database-url>=2.1,<3.0
psycopg2-binary>=2.9,<3.0
celery[redis]>=5.4,<6.0
django-celery-beat>=2.6,<3.0
redis>=5.0,<6.0
nanoid>=2.0,<3.0
```

**dev.txt:**
```
-r base.txt
pytest>=8.0,<9.0
pytest-django>=4.8,<5.0
pytest-celery>=1.0,<2.0
factory-boy>=3.3,<4.0
flake8>=7.0,<8.0
```

**prod.txt:**
```
-r base.txt
gunicorn>=22.0,<23.0
whitenoise>=6.5,<7.0
```

- **Acceptance criteria:**
  - `pip install -r requirements/dev.txt` succeeds in a Python 3.12 environment
  - All three files exist with version pinning as shown
  - `dev.txt` includes `-r base.txt` (inherits base)
  - `prod.txt` includes `-r base.txt`
- **Depends on:** 0.1

---

#### Task 0.3: Dockerfile

Create a Dockerfile optimized for development (requirements as separate layer).

**Specification:**
- Base image: `python:3.12-slim`
- Working directory: `/app`
- System deps: `libpq-dev`, `gcc` (needed for psycopg2)
- Copy `requirements/` first, install with `--no-cache-dir` from `requirements/dev.txt`
- Copy `src/` (overridden by volume mount in dev)
- Set `PYTHONUNBUFFERED=1` and `PYTHONPATH=/app/src`
- Do NOT include `CMD` — each service specifies its own command in docker-compose

Reference the Dockerfile template in the "Docker Dev Setup" section above.

- **Acceptance criteria:**
  - `docker build -t vtaskforge .` completes without errors
  - Image size is reasonable (< 500MB)
  - `docker run --rm vtaskforge python --version` outputs Python 3.12.x
  - `docker run --rm vtaskforge pip list` shows Django, DRF, celery installed
- **Depends on:** 0.2

---

#### Task 0.4: docker-compose.yml

Create docker-compose.yml with all 5 services.

**Services:**

1. **api** — builds from Dockerfile, runs `python src/manage.py runserver 0.0.0.0:8000`, mounts `./src:/app/src`, exposes port 8000, depends on db (healthy) + redis
2. **db** — `postgres:16-alpine`, volume `pgdata`, env: `POSTGRES_DB=vtaskforge`, `POSTGRES_USER=vtf`, `POSTGRES_PASSWORD=vtfdev`, port 5432, healthcheck with `pg_isready -U vtf -d vtaskforge`
3. **redis** — `redis:7-alpine`, port 6379
4. **celery** — same build as api, runs `celery -A vtaskforge worker -l info`, same volume mount, depends on db + redis
5. **celery-beat** — same build as api, runs `celery -A vtaskforge beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`, same volume mount, depends on redis

**All custom services share these env vars:**
- `DJANGO_SETTINGS_MODULE=vtaskforge.settings.dev`
- `DATABASE_URL=postgres://vtf:vtfdev@db:5432/vtaskforge`
- `CELERY_BROKER_URL=redis://redis:6379/0`

**Volume:** `pgdata` (named volume for Postgres data persistence)

Reference the docker-compose.yml template in the "Docker Dev Setup" section above.

- **Acceptance criteria:**
  - `docker compose config` validates without errors
  - `docker compose up -d` starts all 5 services
  - `docker compose ps` shows all 5 services running
  - `docker compose down && docker compose up -d` works without manual steps
  - Postgres healthcheck passes
  - Modifying a `.py` file in `./src/` triggers Django's auto-reloader in the api container
- **Depends on:** 0.3

---

#### Task 0.5: Django project & settings

Create the Django project configuration files.

**Files to create/modify:**

`src/manage.py` — standard Django manage.py, default settings module: `vtaskforge.settings.dev`

`src/vtaskforge/wsgi.py` — standard WSGI config

`src/vtaskforge/urls.py` — URL configuration:
- `/admin/` — Django admin
- `/v1/` — API namespace (empty for now, health endpoint added in task 0.7)
- Default handler for 404 should return JSON, not HTML

`src/vtaskforge/celery.py` — Celery app:
- App name: `vtaskforge`
- Auto-discover tasks from all installed apps
- Load config from Django settings with `CELERY_` prefix

`src/vtaskforge/__init__.py` — import celery app so it's loaded on Django startup

`src/vtaskforge/settings/base.py`:
- `SECRET_KEY` from `os.environ.get('SECRET_KEY', 'dev-insecure-key-change-in-prod')`
- `INSTALLED_APPS`: Django defaults + `rest_framework`, `corsheaders`, `django_celery_beat`, `core`
- `MIDDLEWARE`: include `corsheaders.middleware.CorsMiddleware`
- `DATABASES`: configured via `dj_database_url.config(default=os.environ.get('DATABASE_URL'))`
- `REST_FRAMEWORK`: default renderer = JSON, default parser = JSON
- `CELERY_BROKER_URL` from env
- `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`
- Custom 404 handler that returns JSON

`src/vtaskforge/settings/dev.py`:
- `from .base import *`
- `DEBUG = True`
- `ALLOWED_HOSTS = ['*']`
- `CORS_ALLOW_ALL_ORIGINS = True`

`src/vtaskforge/settings/prod.py`:
- `from .base import *`
- `DEBUG = False`
- `ALLOWED_HOSTS` from env (comma-separated)
- `CORS_ALLOW_ALL_ORIGINS = False`

- **Acceptance criteria:**
  - `docker compose exec api python src/manage.py check` passes with no warnings
  - `docker compose exec api python src/manage.py migrate` runs without errors
  - Django admin accessible at `http://localhost:8000/admin/`
  - `http://localhost:8000/nonexistent` returns JSON 404, not HTML
  - No hardcoded secrets in `base.py` (SECRET_KEY from env)
  - `DJANGO_SETTINGS_MODULE` correctly resolves to dev settings in container
- **Depends on:** 0.4

---

#### Task 0.6: Core app — mixins

Create reusable model mixins in `src/core/mixins.py`.

**NanoIDMixin:**
- Generates a nanoid as the primary key (`id` field)
- Use the `nanoid` Python package
- ID length: 21 characters (nanoid default)
- Field type: `CharField(max_length=21, primary_key=True, default=generate_nanoid, editable=False)`
- The `generate_nanoid` function should be a module-level callable (not a lambda) so Django can serialize it in migrations

**TimestampMixin:**
- `created_at = DateTimeField(auto_now_add=True)`
- `updated_at = DateTimeField(auto_now=True)`

Both mixins should be abstract models (`class Meta: abstract = True`).

**Files:**
- Create `src/core/mixins.py`
- Update `src/core/__init__.py` if needed

**Test file:** `tests/test_mixins.py`
- Test that NanoIDMixin generates a 21-char string ID
- Test that two generated IDs are different (uniqueness)
- Test that TimestampMixin fields are auto-populated

- **Acceptance criteria:**
  - `from core.mixins import NanoIDMixin, TimestampMixin` works
  - NanoID generates 21-character alphanumeric strings
  - Two calls to `generate_nanoid()` produce different values
  - TimestampMixin has `created_at` and `updated_at` fields with `auto_now_add` and `auto_now`
  - All tests in `tests/test_mixins.py` pass
- **Depends on:** 0.5

---

#### Task 0.7: Core app — health endpoint

Create `GET /v1/health` endpoint that checks DB and Redis connectivity.

**Files:**
- Create `src/core/views.py` — health check view
- Update `src/vtaskforge/urls.py` — wire `/v1/health` route

**View implementation:**
- Use a DRF `APIView` (not a viewset — this is a simple endpoint)
- Check DB: execute `django.db.connection.ensure_connection()` inside a try/except
- Check Redis: use `django.core.cache` or direct `redis.Redis` connection ping
- Response format:
  ```json
  {
    "status": "healthy",
    "checks": {
      "db": "ok",
      "redis": "ok"
    }
  }
  ```
- If any check fails, return HTTP 503 with the failing check showing `"error: <message>"`:
  ```json
  {
    "status": "unhealthy",
    "checks": {
      "db": "ok",
      "redis": "error: Connection refused"
    }
  }
  ```
- No authentication required on this endpoint

**URL wiring:**
- `src/vtaskforge/urls.py` should include a `/v1/` namespace
- Health endpoint at `/v1/health`

- **Acceptance criteria:**
  - `curl http://localhost:8000/v1/health` returns `200` with `{"status": "healthy", "checks": {"db": "ok", "redis": "ok"}}`
  - Stopping the db container and hitting `/v1/health` returns `503` with db showing error
  - Stopping the redis container and hitting `/v1/health` returns `503` with redis showing error
  - Response content-type is `application/json`
- **Depends on:** 0.5

---

#### Task 0.8: Celery setup

Configure Celery with a test task to verify the worker pipeline works.

**Files:**
- `src/vtaskforge/celery.py` should already exist from task 0.5 — verify it auto-discovers tasks
- Create `src/core/tasks.py` — test task:
  ```python
  from vtaskforge.celery import app

  @app.task
  def add(x, y):
      return x + y
  ```

**Verification approach:**
- From Django shell (`manage.py shell`):
  ```python
  from core.tasks import add
  result = add.delay(2, 3)
  print(result.get(timeout=10))  # Should print 5
  ```
- Celery worker logs should show the task being received and completed

**Celery beat:**
- `django-celery-beat` should be installed and migrated (tables created)
- Beat starts without errors — no scheduled tasks needed in Phase 0, just verify the scheduler boots

- **Acceptance criteria:**
  - `docker compose logs celery` shows "celery@... ready" message
  - `docker compose logs celery-beat` shows beat starting without errors
  - From Django shell: `add.delay(2, 3).get(timeout=10)` returns `5`
  - Task execution appears in celery worker logs
  - `django_celery_beat` tables exist after migration
- **Depends on:** 0.5

---

#### Task 0.9: Django app stubs

Create 6 app stubs. These are empty shells — no models, views, or serializers. Just the app registration so they're ready for Phase 1.

**Apps to create (under `src/`):**
- `workplans` — label: `workplans`
- `tasks` — label: `tasks`
- `links` — label: `links`
- `reviews` — label: `reviews`
- `events` — label: `events`
- `agents` — label: `agents`

**Each app needs:**
- `__init__.py` (empty, should already exist from task 0.1)
- `apps.py` with `AppConfig`:
  ```python
  from django.apps import AppConfig

  class WorkplansConfig(AppConfig):
      default_auto_field = 'django.db.models.BigAutoField'
      name = 'workplans'
  ```

**Update `INSTALLED_APPS` in `src/vtaskforge/settings/base.py`** to include all 7 apps:
```python
LOCAL_APPS = [
    'core',
    'workplans',
    'tasks',
    'links',
    'reviews',
    'events',
    'agents',
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
```

- **Acceptance criteria:**
  - `docker compose exec api python src/manage.py check` passes with no warnings
  - All 7 apps appear in the Django app registry
  - No models, views, serializers, or URLs in the stub apps — just `__init__.py` and `apps.py`
- **Depends on:** 0.5

---

#### Task 0.10: Test suite setup

Set up pytest-django and write smoke tests for health endpoint and Celery.

**Files:**
- `src/conftest.py` or `tests/conftest.py` — pytest-django configuration:
  ```python
  import pytest

  @pytest.fixture(scope='session')
  def django_db_setup():
      pass  # Use default test DB settings

  # Set DJANGO_SETTINGS_MODULE
  ```
- `pytest.ini` or `pyproject.toml` — pytest config with `DJANGO_SETTINGS_MODULE = vtaskforge.settings.dev`
- `tests/test_health.py` — health endpoint tests
- `tests/test_celery.py` — celery task test

**Tests to write:**

`tests/test_health.py`:
1. `test_health_returns_200` — `GET /v1/health` returns 200 with both checks "ok"
2. `test_health_returns_503_when_db_down` — mock DB connection to raise, verify 503 with db error
3. `test_health_returns_503_when_redis_down` — mock Redis connection to raise, verify 503 with redis error
4. `test_health_response_format` — verify JSON structure matches expected format

`tests/test_celery.py`:
1. `test_add_task` — call `add(2, 3)` synchronously (use `CELERY_TASK_ALWAYS_EAGER=True` in test settings), verify returns 5

**Testing approach:**
- Use `pytest-django`'s `client` fixture for HTTP tests
- Use `CELERY_TASK_ALWAYS_EAGER = True` for celery tests (runs tasks synchronously, no Redis needed in tests)
- Mock DB/Redis failures using `unittest.mock.patch`

- **Acceptance criteria:**
  - `docker compose exec api pytest` runs and discovers all tests
  - All tests pass (minimum 5 tests)
  - Tests use a separate test database (not the dev database)
  - Celery tests don't require a running Redis (eager mode)
  - `pytest` output shows test names and pass/fail status
- **Depends on:** 0.7, 0.8

---

#### Task 0.11: CLAUDE.md & documentation

Create `CLAUDE.md` in the project root (`/home/jasonvi/GitHub/vtaskforge/CLAUDE.md`).

**Sections to include:**

1. **Project purpose** — one paragraph: "vtaskforge is a distributed task execution system for LLM agents. Django/DRF API server backed by Postgres, with Celery for background processing. See docs/ for full design."

2. **Dev setup:**
   ```
   docker compose up -d
   docker compose exec api python src/manage.py migrate
   docker compose exec api python src/manage.py createsuperuser
   ```

3. **Running tests:**
   ```
   docker compose exec api pytest
   docker compose exec api pytest -v          # verbose
   docker compose exec api pytest tests/test_health.py  # specific file
   ```

4. **Django management commands:**
   ```
   docker compose exec api python src/manage.py <command>
   ```

5. **Rebuilding** — only needed when `requirements/*.txt` changes:
   ```
   docker compose build
   docker compose up -d
   ```

6. **Environment variables:**
   | Variable | Default | Description |
   |---|---|---|
   | `DJANGO_SETTINGS_MODULE` | `vtaskforge.settings.dev` | Settings module |
   | `DATABASE_URL` | `postgres://vtf:vtfdev@db:5432/vtaskforge` | Postgres connection |
   | `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis broker |
   | `SECRET_KEY` | `dev-insecure-key-change-in-prod` | Django secret key |

7. **Project structure** — brief description of Django apps and their purpose

- **Acceptance criteria:**
  - `CLAUDE.md` exists at project root
  - All 7 sections are present
  - Commands in the doc actually work when copy-pasted
  - No references to features that don't exist yet (Phase 0 only)
- **Depends on:** 0.10

#### Dependency DAG

```
0.1 ──→ 0.2 ──→ 0.3 ──→ 0.4 ──→ 0.5 ──┬──→ 0.6
                                         ├──→ 0.7 ──┐
                                         ├──→ 0.8 ──┼──→ 0.10 ──→ 0.11
                                         └──→ 0.9   │
                                                     │
                              (0.7 and 0.8 must both  │
                               complete before 0.10) ─┘
```

Tasks 0.6, 0.7, 0.8, 0.9 can execute in parallel after 0.5 completes.

---

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

Likely scope: Workplan, Phase, Task, Link models + migrations + basic DRF serializers and viewsets. State machine enforcement on Task transitions.

## Phase 2+

*To be planned.*
