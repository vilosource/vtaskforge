# CLAUDE.md

## Project Purpose

vtaskforge is a distributed task execution system for LLM agents. Django/DRF API server backed by Postgres, with Celery for background processing. See `docs/` for full design.

## Dev Setup

```bash
docker compose up -d
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
```

Services started: api (port 8000), db (Postgres, host port 5436), redis (port 6379), celery worker, celery-beat.

## Running Tests

```bash
docker compose exec api pytest                         # all tests
docker compose exec api pytest -v                      # verbose
docker compose exec api pytest tests/test_health.py    # specific file
docker compose exec api pytest tests/test_mixins.py    # mixin tests
docker compose exec api pytest tests/test_celery.py    # celery tests
```

Test configuration lives in `pyproject.toml`. Tests use `pytest-django` with a separate test database. Celery tests run in eager mode (no Redis required).

## Django Management Commands

All management commands run inside the api container:

```bash
docker compose exec api python src/manage.py <command>
```

Common commands:

```bash
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
docker compose exec api python src/manage.py shell
docker compose exec api python src/manage.py check
```

## Rebuilding

Only needed when `requirements/*.txt` files change:

```bash
docker compose build
docker compose up -d
```

Source code changes are picked up automatically via volume mount and Django's auto-reloader.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `vtaskforge.settings.dev` | Settings module |
| `DATABASE_URL` | `postgres://vtf:vtfdev@db:5432/vtaskforge` | Postgres connection (internal to Docker network) |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Redis broker URL |
| `SECRET_KEY` | `dev-insecure-key-change-in-prod` | Django secret key (must override in production) |

The Postgres port is mapped to **5436** on the host (not 5432) to avoid conflicts. Inside the Docker network, containers connect on port 5432.

## Project Structure

```
src/
  vtaskforge/          # Django project config (settings, urls, celery, wsgi)
    settings/
      base.py          # Shared settings
      dev.py           # Dev overrides (DEBUG=True)
      prod.py          # Production overrides
  core/                # Base model mixins (NanoIDMixin, TimestampMixin), health endpoint, shared utils
  initiatives/         # Initiative + Phase models (stub - Phase 1)
  tasks/               # Task models, state machine (stub - Phase 1)
  links/               # Link system (stub - Phase 1)
  reviews/             # Review system (stub - Phase 1)
  events/              # Task events + SSE (stub - Phase 1)
  agents/              # Agent registration, auth tokens (stub - Phase 1)
tests/                 # pytest-django test suite
requirements/
  base.txt             # Core dependencies
  dev.txt              # Dev/test dependencies (includes base.txt)
  prod.txt             # Production dependencies (includes base.txt)
```

### Useful Endpoints

- `GET /v1/health` -- health check (DB + Redis connectivity)
- `/admin/` -- Django admin interface

### Viewing Logs

```bash
docker compose logs -f api
docker compose logs -f celery
docker compose logs -f celery-beat
```

### Stopping

```bash
docker compose down
```
