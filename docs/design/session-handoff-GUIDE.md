# Session Handoff — 2026-03-20

## Where We Are

vtaskforge has been built across Milestones 0-4 in a single marathon session. Milestone 5 specs are written and imported into the dogfood instance, but execution hasn't started.

### What Exists

**Backend API** (Django/DRF, 669 tests):
- Workplan → Milestone → Task hierarchy with full CRUD
- 11-status task state machine with transition enforcement
- Atomic claiming with tag matching and dependency checking
- Review gates (before start + on completion) with flag cascading
- Append-only event audit log with auto-logging on state changes
- Claim expiry via Celery periodic task
- Token + Session authentication
- Bulk import endpoint (accepts workplan_id for adding milestones to existing workplans)
- Cursor pagination on all list endpoints
- SSE event stream (polling-based)
- `?expand=links,reviews,events` on task detail

**CLI** (`vtf`, 123 tests):
- `vtf workplan create/list/show/archive/complete`
- `vtf task list/show/submit/claim/complete/fail/claimable/events`
- `vtf agent register/list/show/status`
- `vtf workplan stats`, `vtf milestone stats`
- `vtf import <milestone-dir> [--workplan <id>]`
- `vtf config set/show`, `vtf health`

**Web UI** (React + TypeScript + Vite, 78 tests):
- Login page (session auth via Django)
- Workplan list page
- Workplan detail page with milestone overview (progress bars, status badges)
- Kanban board scoped per milestone (6 columns)
- Task detail modal with context-sensitive action buttons
- SSE live indicator (Live/Reconnecting)
- CSS styling with status colors

**Infrastructure:**
- Dev stack: `docker compose up` on port 8000 (source mounted, DEBUG=True)
- Dogfood: `docker compose -f docker-compose.dogfood.yml up` on port 8001 (built image, separate DB)
- Vite dev server: port 3000 (proxies /v1 to 8000)
- `Dockerfile.prod` — multi-stage build (Node builds SPA, Python serves via gunicorn)

**Agent Tooling** (at `~/.claude/agents/`):
- `vtf-executor.md` — implements tasks from YAML specs with blast radius discovery
- `vtf-judge.md` — code reviewer checking design alignment and blast radius coverage
- `vtf-blackbox-tester.md` — E2E scenario tester via curl
- `vtf-supervisor.md` — milestone orchestrator (not yet tested end-to-end)

**Process Documentation** (at `docs/guides/milestone-process-GUIDE.md`):
- Iteration 4 — Gate 1c deployment smoke test
- Blast radius discovery for executors and judges
- Web testing strategy (Vitest + Playwright)
- Testing by project type (backend, frontend, CLI)

### What's on the Dogfood Board

```
Workplan: vtaskforge (TPAfZO6_Ue6OaCaSIIYit)
  Milestone 0 — Project Setup        (6 tasks, pending)
  Milestone 1 — Core Models & CRUD   (11 tasks, pending)
  Milestone 2 — Auth, CLI            (9 tasks, pending)
  Milestone 3 — Polish & Fixes       (6 tasks, pending)
  Milestone 4 — Web UI               (9 tasks, pending)
  Milestone 5 — Polish & DAG View    (6 tasks, pending)  ← NEWLY IMPORTED

Workplan: vf-agents (JQg01rY-kVM2KnQeEZpVr)
  Milestone 1 — Core Runner          (5 tasks, pending)
```

Note: Milestone 0-4 tasks show as "pending" because the fake data didn't fully transition all tasks through claim/complete. The code is all done — it's just the dogfood tracking data that's incomplete.

Milestone 5 tasks are real and ready to execute:
- 5.1: Fix Invalid Date in event timeline
- 5.2: Workplan list — show milestone count + progress
- 5.3: Milestone status management (activate/complete buttons)
- 5.4: Kanban board title shows milestone name
- 5.5: DAG pipeline view (simplified)
- 5.6: Deployment smoke test

## Known Issues to Fix

### 1. SSE under gunicorn (HIGH PRIORITY)
`time.sleep(2)` in the SSE generator blocks gunicorn sync workers. Current band-aid: `--timeout 120`. Proper fix: use `gevent` workers or `uvicorn` with async support. The SSE endpoint needs a non-blocking worker model.

Options:
- `gunicorn -k gevent` — adds `gevent` dependency, async workers
- `uvicorn` — ASGI server, needs Django ASGI app (already has `wsgi.py`, need `asgi.py`)
- `gunicorn -k uvicorn.workers.UvicornWorker` — ASGI via gunicorn

### 2. Invalid Date in event timeline
EventTimeline component parses timestamps incorrectly. The API returns ISO 8601 strings but the component may be looking at the wrong field or not parsing correctly.

### 3. Test isolation
Dev database accumulates data from manual testing (black-box tester, Playwright). Some Django tests fail because they see stale data. Fix: ensure all tests use proper transaction isolation, or flush dev DB before test runs.

### 4. Milestone ordering
Milestones display in reverse creation order (newest first). Should respect the `order` field or creation order.

### 5. Deployment smoke test
`web/tests/deployment-smoke.spec.ts` exists but hasn't been run against the dogfood instance yet. Should be run after every dogfood rebuild.

## How to Continue

### Option A: Execute Milestone 5

```bash
# 1. Resume workspace
kb work start tasktracker

# 2. Read this doc for context
# 3. Check the dogfood board
vtf task list --workplan TPAfZO6_Ue6OaCaSIIYit

# 4. Submit Milestone 5 tasks
for id in tq57yHC285MXA8g-CLQOp -XOgaHVWGLybuxXgJFavc -OsfDphMdcIIh_QWNI7-e Rq8hR9--syS_mGdkUNcRv 5EtcZ4fXBM2IkluBaH0ba rbCWhr-k4mIiLAwPByyOz; do
  vtf task submit $id
done

# 5. Fix SSE properly FIRST (task 0 — before Milestone 5)
# Options: gevent workers, uvicorn, or async Django

# 6. Execute Milestone 5 tasks using standardized executor prompts
# Specs at: ~/GitHub/vtaskforge/milestones/milestone5/tasks/
# Parallel: 5.1, 5.2, 5.3, 5.4 (step 1)
# Sequential: 5.5 (step 2), 5.6 (step 3)

# 7. Rebuild dogfood after each task
docker compose -f docker-compose.dogfood.yml build dogfood-api
docker compose -f docker-compose.dogfood.yml up -d
```

### Option B: Use vtf on a Real Project

Pick an actual project and track it through vtf:
```bash
vtf workplan create --name "my-project" --tags infra
vtf import milestones/my-project-milestone1/ --workplan <id>
```

### Key Files

| File | Purpose |
|---|---|
| `~/GitHub/vtaskforge/` | Main repo (develop branch) |
| `docs/guides/milestone-process-GUIDE.md` | Process guide (Iteration 4) |
| `docs/design/process-retrospective-ANALYSIS.md` | Full retrospective |
| `docs/design/simulation-gap-ANALYSIS.md` | Manual vs automated execution |
| `milestones/milestone5/` | Milestone 5 specs (ready to execute) |
| `web/` | React SPA |
| `cli/` | CLI package |
| `Dockerfile.prod` | Production build |
| `docker-compose.dogfood.yml` | Dogfood stack (port 8001) |
| `~/.claude/agents/vtf-*.md` | Agent tooling |

### Process Learnings (Key Takeaways)

1. **YAML task specs work** — 49/49 first-attempt success with Sonnet
2. **pytest is the primary gate** — everything else is optional
3. **Blast radius discovery** — executor must search for all consumers of changed interfaces, including mocks
4. **Gate 1c (deployment smoke)** — test the built artifact, not just the dev server
5. **Design drift** — task specs individually correct but collectively wrong (import created workplans instead of milestones)
6. **Environment boundaries** — things that work in dev break in production (MIME types, SSE, auth flow)
