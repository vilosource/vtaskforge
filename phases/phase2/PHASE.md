# Phase 2 — Auth, Claim Expiry, Bulk Import, CLI

Status: Planning

## Goal

Add the safety and operational infrastructure that makes vtaskforge usable beyond development:

1. **Authentication** — all endpoints require Bearer tokens (except health and agent registration)
2. **Claim expiry** — background Celery task reclaims stuck tasks from unresponsive agents
3. **Bulk import** — atomic creation of workplan structures from intake tooling
4. **CLI (`vtf`)** — command-line interface for all CRUD and lifecycle operations
5. **Test infrastructure** — factory_boy factories and shared fixtures for maintainable tests

## Scope

- 10 tasks total
- Server-side: test factories, claim expiry, authentication, bulk import (4 tasks)
- CLI: core setup, workplan/task/agent commands, import command (5 tasks)
- Verification: black-box test suite (1 task)

## Task Index

| ID   | Name                           | Depends On | Judge | Isolation  | Status  |
|------|--------------------------------|------------|-------|------------|---------|
| 2.1  | Test factory infrastructure    | —          | Yes   | sequential | Pending |
| 2.2  | Claim expiry (Celery task)     | 2.1        | Yes   | sequential | Pending |
| 2.3  | Authentication (TokenAuth)     | 2.1        | Yes   | sequential | Pending |
| 2.4  | Bulk import endpoint           | 2.3        | Yes   | sequential | Pending |
| 2.5  | CLI core — project setup       | 2.3        | Yes   | sequential | Pending |
| 2.6  | CLI — workplan commands         | 2.5        | No    | worktree   | Pending |
| 2.7  | CLI — task commands             | 2.5        | No    | worktree   | Pending |
| 2.8  | CLI — agent commands            | 2.5        | No    | worktree   | Pending |
| 2.9  | CLI — import command            | 2.4, 2.5   | No    | sequential | Pending |
| 2.10 | Black-box test suite            | 2.9        | No    | sequential | Pending |

## DAG

```
2.1 (Test factories)
 ├──> 2.2 (Claim expiry)
 └──> 2.3 (Auth) ──┬──> 2.4 (Bulk import) ────────────────┐
                    └──> 2.5 (CLI core) ──┬──> 2.6 (CLI workplan)  ──┐
                                          ├──> 2.7 (CLI task)        ├──> 2.9 (CLI import) ──> 2.10 (Black-box)
                                          └──> 2.8 (CLI agent)      ──┘
```

## Execution Order

Respecting dependencies and maximizing parallelism:

```
Step 1:  2.1  (Test factories)               — sequential, foundation
Step 2:  2.2 || 2.3                          — parallel, different concerns
Step 3:  2.4 || 2.5                          — parallel, server vs CLI
Step 4:  2.6 || 2.7 || 2.8                   — parallel (worktree isolation)
Step 5:  2.9  (CLI import)                   — sequential, needs 2.4 + 2.5
Step 6:  2.10 (Black-box tests)              — sequential, verification
```

Total sequential steps: 6 (vs 10 if fully sequential).

## Parallel Execution Notes

### First use of worktree isolation (2.6, 2.7, 2.8)

Tasks 2.6, 2.7, and 2.8 are the first time we use git worktree isolation for parallel execution. Each task creates files in a different CLI command module with zero file overlap:

- 2.6: `cli/vtf/commands/workplan.py` + `cli/tests/test_workplan_commands.py`
- 2.7: `cli/vtf/commands/task.py` + `cli/tests/test_task_commands.py`
- 2.8: `cli/vtf/commands/agent.py` + `cli/tests/test_agent_commands.py`

**Shared file risk**: All three modify `cli/vtf/cli.py` (to register their command group). Each adds a single `cli.add_command(...)` line. This is a known merge point — the supervisor merges worktree branches one at a time and resolves any conflicts.

### Parallel opportunities at Step 2

Tasks 2.2 (claim expiry) and 2.3 (auth) modify different files:
- 2.2: `src/tasks/celery_tasks.py`, `src/vtaskforge/settings/base.py` (CELERY_BEAT_SCHEDULE)
- 2.3: `src/vtaskforge/settings/base.py` (REST_FRAMEWORK, INSTALLED_APPS), all test files

**Shared file risk**: Both modify `settings/base.py` but in different sections. Sequential execution is safer here since 2.3 touches all test files and benefits from 2.1's factories being fully landed.

## Key Design Decisions

1. **CLI is a separate package** — lives in `cli/` at repo root, not inside Django `src/`. Installed via `pip install -e cli/`. No imports from the Django project.

2. **Click over Typer** — Click is mature, explicit, and doesn't add magic. Same Python ecosystem as the rest of the project.

3. **DRF TokenAuthentication for v1** — simplest auth that works. Each agent gets a token at registration. Upgrade path to OAuth2/JWT exists but is not needed for v1.

4. **Bulk import in core app** — not a separate Django app. The endpoint is in `src/core/views.py` alongside health. It orchestrates models from workplans, tasks, and links apps.

5. **Agent registration returns token** — the register endpoint is unauthenticated (AllowAny) and returns the token in the response. This is the bootstrap mechanism for agents.

6. **Test factories before everything** — task 2.1 establishes the factory pattern that all subsequent tasks use. This prevents the inline-setup sprawl that made Phase 1 tests harder to maintain.

7. **Claim expiry via Celery Beat** — uses CELERY_BEAT_SCHEDULE in settings, not django_celery_beat database scheduler. Simpler, config-driven, no admin UI needed.

## Contracts Established

| Contract | Task | Description |
|----------|------|-------------|
| test-factory-pattern | 2.1 | All tests use conftest fixtures and factories |
| claim-expiry | 2.2 | Expired claims move to needs_attention with claim_expired event |
| auth-token | 2.3 | All endpoints require Bearer token except health and agent register |
| bulk-import | 2.4 | POST /v1/bulk/import creates workplan structure atomically |
| cli-pattern | 2.5 | Click group + subcommands, API client, config management |

## Contracts Modified

| Contract | Task | Change |
|----------|------|--------|
| agent-registration | 2.3 | POST /v1/agents/ now returns token field in response |
