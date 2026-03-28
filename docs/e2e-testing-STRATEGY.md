# vtf End-to-End Testing Strategy

## Testing Layers

vtf has four testing layers, each with a distinct purpose:

| Layer | Count | What it tests | When it runs |
|-------|-------|--------------|-------------|
| **Unit tests** | 1105 | Models, services, serializers, state machine | Every commit |
| **Frontend tests** | 122 | React components, API hooks, rendering | Every commit |
| **Local E2E** | TBD | Full stack in isolation (API + MCP + DB) | Before merging to develop |
| **Post-deploy smoke** | TBD | Live environment health + critical paths | After every deploy to dev/prod |

Unit and frontend tests exist. This document defines the local E2E and post-deploy smoke layers.

---

## Local E2E Tests

### Purpose

Prove the full stack works together in a production-like deployment before code reaches dev. Catches deployment-level bugs (container startup, service discovery, auth, migration) that unit tests miss.

### Architecture

```
Host machine
  pytest tests/e2e/
    ├── MCP client → localhost:18002 → mcp container
    └── REST client → localhost:18000 → api container

docker-compose.e2e.yml
  ├── db      (postgres, tmpfs — ephemeral)
  ├── api     (Django REST, port 18000)
  └── mcp     (MCP server, port 18002)
```

Isolated from the dev stack (different ports, separate DB). Ephemeral — destroyed on teardown.

### Dual Verification

Every scenario verifies through two independent channels:
1. **MCP response** — the tool returned success with expected data
2. **REST API query** — GET confirms actual DB state

If MCP says "claimed" but REST shows "todo", the test fails.

### Lifecycle

```bash
make e2e
# or manually:
docker compose -f docker-compose.e2e.yml up -d --build --wait
docker compose -f docker-compose.e2e.yml exec api python src/manage.py migrate --run-syncdb
docker compose -f docker-compose.e2e.yml exec api python -c "exec(open('/app/tests/e2e/seed.py').read())"
pytest tests/e2e/ -v --tb=short
docker compose -f docker-compose.e2e.yml down -v
```

### Test Structure

```
tests/e2e/
  conftest.py                        # Stack lifecycle, MCP/REST clients, seed
  seed.py                            # Known test state: project, milestones, tasks, agent
  mcp_client.py                      # MCP HTTP client with available_actions helper
  rest_client.py                     # REST API client for verification
  test_executor_scenario.py          # Executor: poll → claim → work → submit
  test_supervisor_scenario.py        # Supervisor: board → search → review
  test_lifecycle_scenario.py         # Full: create → submit → claim → complete → done
  test_rework_scenario.py            # Rework: complete → reject → reclaim → complete → approve
  test_milestone_enforcement.py      # Milestone gates: submit, claimable, auto-complete
  test_error_recovery.py             # Error paths: bad state, auth, not found
```

### Scenarios

#### Executor workflow
```
next_work → claim_and_start → report_progress → submit_work
```
Verify: task moves todo → doing → done/pending_completion_review. Dual verified via REST.

#### Supervisor workflow
```
board_overview → search_tasks → task_detail → review_task(approved)
```
Verify: pending_completion_review → done. Dual verified via REST.

#### Full lifecycle
```
manage_task(create) → submit → claim → progress → submit_work → review(approve)
```
Verify every state transition via REST at each step.

#### Rework flow
```
create → submit → claim → complete → review(changes_requested) → claim → complete → review(approved)
```
Verify:
- Task goes to changes_requested after rejection
- Any executor can claim a changes_requested task (not just original)
- Task completes after rework approval

#### Milestone enforcement
```
Scenario A: Submit blocked on pending milestone
  create milestone (pending) → create task → submit → expect 409 MILESTONE_NOT_ACTIVE

Scenario B: Claimable filters out pending milestone tasks
  create pending milestone with todo task (via reset) → claimable → not returned
  create active milestone with todo task → claimable → returned

Scenario C: Auto-complete
  create pending milestone → create tasks → reset all to done → milestone status = completed

Scenario D: Activate skips to completed
  create pending milestone with all-done tasks → activate → status = completed
```

#### Error recovery
- Claim nonexistent task → error with recovery actions
- Claim already-claimed task → error with guidance
- Submit work on non-doing task → error
- Review non-review task → error
- No auth token → 401

### What's NOT in local E2E

- **CXDB** — not in the local stack. Trace integration tested via post-deploy smoke only.
- **Executor agent** — no real Claude Code invocation. Scenarios simulate the API calls an executor makes.
- **Frontend** — covered by vitest unit tests (122 tests).
- **LLM-in-the-loop** — too expensive and non-deterministic for CI.

---

## Post-Deploy Smoke Tests

### Purpose

Verify a deployment is healthy and the integrated stack works. Runs against the live dev or prod environment after `release.sh` deploys. Gates prod promotion.

### Architecture

```
scripts/smoke-test.sh <dev|prod>
  ├── Health check (API + MCP endpoints)
  ├── CRUD smoke (create task, read, update, delete)
  ├── CXDB connectivity (expand=traces returns data or graceful null)
  └── Milestone enforcement (submit blocked on pending)
```

Runs from the developer's machine or CI against the deployed URL. Uses auth tokens, not direct DB access.

### Smoke Test Suite

#### 1. Health
- `GET /v1/health` → `{"status":"healthy","checks":{"db":"ok","redis":"ok"}}`

#### 2. Auth
- Request without token → 401
- Request with valid token → 200

#### 3. CRUD
- Create a task → 201
- Read the task → 200, fields match
- Update the task → 200
- Delete the task → 204 or 200

#### 4. State machine
- Create + submit → todo
- Submit on pending milestone → 409

#### 5. CXDB integration
- `GET /v1/tasks/{known-task}/?expand=traces` → traces field present (list or null, not error)

#### 6. Claimable
- `GET /v1/tasks/claimable/` → 200, returns list

### When smoke tests run

| Event | Runs against | Blocks |
|-------|-------------|--------|
| `release.sh dev` completes | vtf.dev.viloforge.com | Nothing (informational) |
| Before `release.sh prod` | vtf.dev.viloforge.com | Prod deploy (must pass) |
| `release.sh prod` completes | vtf.viloforge.com | Nothing (informational) |

### Smoke test script

```bash
scripts/smoke-test.sh dev   # → runs against vtf.dev.viloforge.com
scripts/smoke-test.sh prod  # → runs against vtf.viloforge.com
```

Exit code 0 = all pass. Non-zero = failures. Output shows each check with pass/fail.

---

## Release Process

The complete release process with testing gates:

```
1. Develop feature on branch
2. Unit tests pass (1105+)          ← pytest tests/
3. Frontend tests pass (122+)       ← npx vitest run
4. Local E2E pass                   ← make e2e
5. Merge to develop
6. Deploy to dev                    ← release.sh dev
7. Post-deploy smoke (dev)          ← smoke-test.sh dev
8. Manual verification if needed    ← browser, MCP tools
9. Deploy to prod                   ← release.sh prod
10. Post-deploy smoke (prod)        ← smoke-test.sh prod
```

Steps 2-4 gate the merge. Steps 7 gates prod deploy. Step 10 confirms prod.

---

## Implementation Order

| Phase | What | Effort |
|-------|------|--------|
| **Phase 1** | Post-deploy smoke script (`scripts/smoke-test.sh`) | Small — curl + assertions |
| **Phase 2** | Local E2E infrastructure (compose, conftest, seed, clients) | Medium |
| **Phase 3** | Core scenarios (executor, lifecycle, rework) | Medium |
| **Phase 4** | Enforcement + error scenarios | Small |
| **Phase 5** | Integrate into release.sh | Small — call smoke-test.sh after deploy |
| **Phase 6** | CI integration | Future — when CI pipeline exists |

Phase 1 (smoke script) is highest value per effort — we can start using it immediately after every deploy. Phase 2-3 is the local E2E foundation.
