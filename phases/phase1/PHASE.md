# Phase 1 — Core Models & Basic CRUD

Status: Complete (2026-03-20)

## Goal

All domain models exist in the database with migrations, DRF serializers/viewsets expose CRUD endpoints, and the task state machine enforces valid transitions. Review gates work with flag cascading, and atomic claiming prevents race conditions.

## Scope

- Workplan, Phase, Task, Agent models + migrations
- Link model (generic relationship system)
- Note, Review, TaskEvent models
- Task state machine with all 11 statuses and full transition enforcement
- Basic CRUD endpoints for all models
- Task lifecycle actions (submit, claim, complete, fail, block, etc.)
- Atomic task claiming with conflict handling and dependency checks
- Review flag cascading (task > phase > workplan)
- Append-only event audit log with auto-logging on state transitions

## Tasks

| ID | Name | Depends On | Status |
|----|------|-----------|--------|
| 1.1 | Workplan model + CRUD | — | pending |
| 1.2 | Agent model + registration | 1.1 | pending |
| 1.3 | Phase model + CRUD | 1.1 | pending |
| 1.4 | Task model (model only) | 1.3 | pending |
| 1.5 | Task state machine | 1.4 | pending |
| 1.6 | Task CRUD + lifecycle endpoints | 1.5, 1.2 | pending |
| 1.7 | Link model + CRUD | 1.4 | pending |
| 1.8 | Note model + endpoints | 1.6 | pending |
| 1.9 | Review model + endpoints | 1.6 | pending |
| 1.10 | TaskEvent model + auto-logging | 1.6 | pending |
| 1.11 | Review flag cascading | 1.9 | pending |
| 1.12 | Atomic claim + dependency check | 1.7, 1.10 | pending |

## DAG

```
1.1 (Workplan) ──┬──> 1.3 (Phase) ──> 1.4 (Task model) ──┬──> 1.5 (State machine) ──> 1.6 (Task CRUD) ──┬──> 1.8 (Note)
                 │                                         │                                              ├──> 1.9 (Review) ──> 1.11 (Cascading)
                 │                                         │                                              └──> 1.10 (Event) ──┐
                 │                                         └──> 1.7 (Link) ───────────────────────────────────────────────────┴──> 1.12 (Atomic claim)
                 │
                 └──> 1.2 (Agent) ──> 1.6 (also depends on Agent)
```

### Execution order (all sequential due to shared file risks)

```
1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9 → 1.10 → 1.11 → 1.12
```

Note: 1.2 and 1.3 could theoretically run in parallel (both depend only on 1.1), but both modify `vtaskforge/urls.py`, so they run sequentially. Similarly, 1.7 could start after 1.4, but sequential execution is safer given shared files.

## Models by App

| App | Models | Created in |
|-----|--------|-----------|
| workplans | Workplan, Phase | 1.1, 1.3 |
| agents | Agent | 1.2 |
| tasks | Task, Note | 1.4, 1.8 |
| links | Link | 1.7 |
| reviews | Review | 1.9 |
| events | TaskEvent | 1.10 |

## Key Design Decisions

- **Phase in workplans app** — Phase belongs to Workplan in the domain hierarchy, so it lives in the same Django app.
- **Note in tasks app** — Notes are task-specific, so they live alongside Task.
- **Link uses string references** — No FK to source/target, uses source_type+source_id for flexibility with external references.
- **All sequential isolation** — Every task modifies shared files (urls.py, settings, or files created by prior tasks). Safer to run sequentially.
- **State machine is standalone module** — Not a model method, not middleware. Clean function that validates and performs transitions.
