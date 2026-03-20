# vtaskforge — Workplan

## Project Purpose

vtaskforge is a distributed task execution system for LLM agents. It provides a Postgres-backed API server (Django/DRF) with Celery for background processing. Agents claim tasks from a pool, execute them, and report results. The system manages the full task lifecycle — from draft through review, execution, and completion — with structured handoff context so any agent can pick up any task cold.

## Goals

- Structured workplans with phases and tasks, each task being a self-contained agent work packet
- Atomic task claiming with conflict handling (two agents racing: one wins, one gets 409)
- Review gates before task start and on completion, with cascading defaults
- KB area linking so agents can `kb load` relevant context before executing
- Real-time event stream for live board updates as agents claim and complete tasks
- Both terminal UI and web UI consuming the same API

## Architecture Decisions Summary

See [docs/design/vtaskforge-DESIGN.md](docs/design/vtaskforge-DESIGN.md) for full design.

Key decisions:
- **Stack**: Django 5.1 + DRF, Postgres 16, Celery + Redis
- **Storage**: Postgres as central store — multiple agents on different machines need shared access
- **Communication**: REST + SSE for all agent/UI interaction — location-agnostic from day one
- **Task distribution**: Pull (agents claim from pool) + push (pinned assignment) model
- **Agent matching**: Three levels — open (any agent), tagged (requires tags), pinned (specific agent)
- **Atomic claims**: Postgres UPDATE with WHERE clause — no locks needed, MVCC handles races
- **Auth**: DRF TokenAuthentication for v1, pluggable for future OAuth2/JWT

## Phase Index

| Phase | Directory | Status | Goal |
|-------|-----------|--------|------|
| Phase 0 — Project Setup | [phases/phase0/](phases/phase0/) | Complete | Django skeleton boots in Docker with health endpoint and Celery connected |
| Phase 1 — Core Models & CRUD | [phases/phase1/](phases/phase1/) | Complete | All domain models, migrations, DRF endpoints, task state machine |
| Phase 2 — Auth, Claim Expiry, Bulk Import, CLI | [phases/phase2/](phases/phase2/) | Complete | Authentication, claim expiry, bulk import, CLI (`vtf`), test factories |
| Phase 3 — Polish, Fixes, Operational Features | [phases/phase3/](phases/phase3/) | Planning | Fix unclaim/claim bugs, real stats, cursor pagination, SSE stream, CLI commands. Pipeline validation (dogfooding). |
| Phase 4 — Web UI (React SPA) | [phases/phase4/](phases/phase4/) | Planning | Kanban board, task detail modal, SSE live updates, production build |
