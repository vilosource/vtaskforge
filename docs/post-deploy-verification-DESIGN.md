# Post-Deploy Verification Suite — Design

## Problem

After every deployment to prod (or dev), we manually browse the UI to verify
features still work. This is tedious, inconsistent, and easy to skip. The
existing Playwright tests (28 tests across 5 files) were written for local
development — they target localhost, assume pre-seeded data, and test
individual component behaviors rather than end-to-end user journeys.

## What Exists Today

| Suite | Target | Focus | Tests |
|-------|--------|-------|-------|
| `deployment-smoke.spec.ts` | `localhost:8001` (dogfood) | Login, assets, MIME, health, SSE | 7 |
| `kanban.spec.ts` | `localhost:3000` (Vite dev) | Column rendering, card clicks | 3 |
| `workplan-list.spec.ts` | `localhost:3000` | Table rendering, navigation | 2 |
| `task-detail.spec.ts` | `localhost:3000` | Modal open/close | 2 |
| `user-management.spec.ts` | `localhost:8001` (dogfood) | Profile, admin, service accounts | 14 |

**Why these can't run against prod as-is:**

1. **No data** — kanban, workplan, and task tests skip when no data exists.
   Prod board is empty after a fresh deploy.
2. **Hardcoded credentials** — `admin/admin` for dogfood, prod has different
   passwords.
3. **Hardcoded URLs** — `localhost:3000` or `localhost:8001`.
4. **Data mutation without cleanup** — service account creation, channel
   mapping creation leave artifacts behind.
5. **Wrong abstraction level** — testing individual modals and buttons, not
   "can a user accomplish their goal?"

## What We Need

A **journey-level** verification suite that:

- Runs against any environment (dev, prod, staging) via environment variables
- Seeds its own test data via the API, then cleans up
- Tests complete user workflows, not individual widgets
- Reports pass/fail with screenshots on failure
- Integrates into `release.sh` as a final gate

## Test Architecture

```
web/
  e2e/
    verify/
      playwright.config.ts       # Env-aware config, no webServer needed
      global-setup.ts            # Seed verification project + data via API
      global-teardown.ts         # Delete verification project
      helpers/
        api.ts                   # API client for seed/cleanup
        auth.ts                  # Login helper, storageState reuse
      journeys/
        01-auth.spec.ts          # Authentication journey
        02-navigation.spec.ts    # Sidebar + page routing journey
        03-project.spec.ts       # Project → workplan → kanban journey
        04-task.spec.ts          # Task detail journey
        05-admin.spec.ts         # Admin pages journey
        06-api-health.spec.ts    # API + SSE infrastructure checks
```

### Why this structure?

- **Separate from dev tests** — different config, different concerns, different
  lifecycle. Dev tests run during development; verify tests run after deploy.
- **Numbered journey files** — enforce execution order. Auth must pass before
  navigation tests make sense. Not because of shared state, but because a
  failure in auth makes later failures noise.
- **`global-setup`/`global-teardown`** — single place to seed and clean the
  verification project. Tests don't create their own data.
- **`helpers/auth.ts`** — login once, save `storageState`, reuse across all
  journey files. Avoids logging in per-test.

## Test Data Strategy

### Seed (global-setup)

Create via REST API using admin token:

1. **Project**: `_verify` (name: "Verification Project")
2. **Workplan**: `_verify-wp` under project, with title "Verify Workplan"
3. **Milestone**: `_verify-m1` under workplan, status active
4. **Tasks** (6, one per kanban column):
   - `verify-draft` → status: draft
   - `verify-review` → status: needs_review
   - `verify-ready` → status: todo
   - `verify-doing` → status: in_progress (needs a claimed agent)
   - `verify-attention` → status: needs_attention
   - `verify-done` → status: done
5. **Agent**: `verify-agent` (for claiming the in-progress task)
6. **Non-staff user**: `verify-viewer` (for permission tests)

### Cleanup (global-teardown)

Delete in reverse order: tasks, milestone, workplan, project, agent, user.
Tolerate 404s (idempotent cleanup).

### Why API-seeded, not UI-seeded?

- **Speed** — API calls take milliseconds vs. seconds per form fill.
- **Reliability** — no flaky selectors, no timing issues.
- **Separation of concerns** — the seed is not what we're testing.
- **Idempotent** — can detect if verification data already exists and skip or
  recreate.

### Naming convention

All verification entities use the `_verify` prefix. This makes them:
- Easy to identify visually if cleanup fails
- Easy to find with a glob query for manual cleanup
- Unlikely to collide with real data

## Journey Specifications

### Journey 1: Authentication (`01-auth.spec.ts`)

**Persona:** Any user arriving at the system.

| # | Step | Assertion |
|---|------|-----------|
| 1 | Navigate to base URL (unauthenticated) | Redirected to `/login` |
| 2 | Verify login page elements | "VTaskForge" branding, username/password fields, "Sign in" button visible |
| 3 | Login with invalid credentials | Error message shown, stays on `/login` |
| 4 | Login with valid credentials | Redirected to `/`, no longer on `/login` |
| 5 | Verify authenticated state | Username or avatar shown in sidebar/header |
| 6 | Verify token validation | `GET /v1/auth/validate/` returns 200 with correct user_id |

**Why this matters post-deploy:** Auth is the gate to everything. If login
breaks, nothing else works. Migration issues, secret key changes, session
backend problems all surface here.

### Journey 2: Navigation (`02-navigation.spec.ts`)

**Persona:** Authenticated user exploring the app.

| # | Step | Assertion |
|---|------|-----------|
| 1 | Verify sidebar links present | Projects, Agents, Settings links visible |
| 2 | Click Projects | URL is `/projects`, page renders without errors |
| 3 | Click Agents | URL is `/agents`, page renders |
| 4 | Click Settings | URL is `/settings`, profile page renders |
| 5 | Navigate to home (logo/brand click) | URL is `/` |
| 6 | Console error audit | Zero critical console errors across all navigations |

**Why this matters post-deploy:** Broken imports, missing chunks, or routing
regressions show up as white screens. This catches them all in one sweep.

### Journey 3: Project → Workplan → Kanban (`03-project.spec.ts`)

**Persona:** Operator checking on work progress.

| # | Step | Assertion |
|---|------|-----------|
| 1 | Navigate to `/projects` | Project list loads, `_verify` project visible |
| 2 | Click into `_verify` project | Dashboard renders, workplan listed |
| 3 | Click into `_verify-wp` workplan | Workplan detail page, milestone listed |
| 4 | Click into `_verify-m1` milestone | Kanban board renders |
| 5 | Verify 6 columns present | draft, review, ready, in-progress, attention, done |
| 6 | Verify tasks in correct columns | Each `verify-*` task appears in its expected column |
| 7 | Breadcrumb navigation | Breadcrumbs show project → workplan → milestone, links work |

**Why this matters post-deploy:** This is the primary user flow. If the
project → workplan → kanban drill-down breaks, the product is unusable.
Column placement verifies the state machine and serializer are working
correctly.

### Journey 4: Task Detail (`04-task.spec.ts`)

**Persona:** Operator inspecting a specific task.

| # | Step | Assertion |
|---|------|-----------|
| 1 | From kanban, click `verify-draft` task | Task detail modal opens |
| 2 | Verify modal content | Title, status badge, description visible |
| 3 | Close modal with Escape | Modal closes, kanban still visible |
| 4 | Navigate to `/tasks/:id` directly | Full task page renders |
| 5 | Verify task page sections | Spec, metadata, status, history sections present |

**Why this matters post-deploy:** Task detail is where operators and agents
get implementation specs. A broken detail view breaks the entire execution
workflow.

### Journey 5: Admin (`05-admin.spec.ts`)

**Persona:** Admin managing users and system state.

| # | Step | Assertion |
|---|------|-----------|
| 1 | Verify admin section in sidebar | Users, Locks, Channels links visible (staff user) |
| 2 | Navigate to `/manage/users` | User table renders with data |
| 3 | Search for `admin` | Search filters table, admin user visible |
| 4 | Navigate to `/manage/locks` | Locks page renders |
| 5 | Navigate to `/manage/channel-mappings` | Channel mappings page renders |
| 6 | Non-staff cannot access admin | `verify-viewer` user redirected from `/manage/*` |

**Why this matters post-deploy:** Admin pages use different API endpoints
and permissions. A migration or permission change could break these without
affecting the main UI.

### Journey 6: API & Infrastructure (`06-api-health.spec.ts`)

**Persona:** System (automated checks).

| # | Step | Assertion |
|---|------|-----------|
| 1 | `GET /v1/health` | 200, db: ok, redis: ok |
| 2 | `GET /v1/projects/` (authenticated) | 200, returns array with `_verify` project |
| 3 | `GET /v1/tasks/?status=draft` (authenticated) | 200, returns results |
| 4 | SSE endpoint accepts connection | 200 with text/event-stream, not 406 |
| 5 | Static asset MIME types | JS files serve as `application/javascript` |
| 6 | SPA fallback routing | Unknown path returns index.html (200), not 404 |

**Why this matters post-deploy:** Catches infrastructure-level breaks:
database connection, Redis, SSE, static file serving, nginx/traefik routing.
These are invisible in the UI but break agents and integrations.

## Environment Configuration

```bash
# Usage:
VTF_BASE_URL=https://vtf.viloforge.com \
VTF_ADMIN_USER=admin \
VTF_ADMIN_PASSWORD=<password> \
VTF_API_TOKEN=<token> \
npx playwright test --config=e2e/verify/playwright.config.ts
```

| Variable | Purpose | Default |
|----------|---------|---------|
| `VTF_BASE_URL` | Target environment URL | `http://localhost:8001` |
| `VTF_ADMIN_USER` | Admin username for UI login | `admin` |
| `VTF_ADMIN_PASSWORD` | Admin password for UI login | `admin` |
| `VTF_API_TOKEN` | API token for seed/cleanup and API tests | (required) |

### Why env vars, not config files?

- No secrets in source control
- Easy to inject in CI/CD
- `release.sh` can pass them inline after deploy

## Integration with release.sh

Add as Step 7 after health checks:

```bash
# Step 7: Post-deploy verification
echo "Running post-deploy verification..."
cd "${VTF_REPO}/web"

VTF_BASE_URL="https://${API_HOST}" \
VTF_ADMIN_USER="admin" \
VTF_ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
VTF_API_TOKEN="${API_TOKEN}" \
npx playwright test --config=e2e/verify/playwright.config.ts \
  --reporter=list 2>&1 | tail -20

VERIFY_EXIT=$?
if [ $VERIFY_EXIT -ne 0 ]; then
    echo "WARNING: Post-deploy verification failed (exit $VERIFY_EXIT)"
    echo "  Review: ${VTF_REPO}/web/e2e/verify/test-results/"
    # Don't exit — deploy succeeded, tests flagged issues
else
    echo "Post-deploy verification passed."
fi
```

### Why warn, not rollback?

- The deploy already happened and is serving traffic.
- Automated rollback is a separate, more dangerous capability.
- The operator should review failures and decide.

## Reliability Principles

1. **No arbitrary sleeps** — use `waitForURL`, `waitForSelector`,
   `expect().toBeVisible({ timeout })`. Network latency to prod is
   higher than localhost.
2. **Generous timeouts** — prod may be slower. Default 15s for page loads,
   10s for element visibility.
3. **Console error collection** — capture but filter noise (favicon,
   manifest, third-party). Fail on application errors.
4. **Screenshot on failure** — Playwright's built-in `screenshot: 'only-on-failure'`
   in config. Saves to `test-results/`.
5. **Trace on failure** — `trace: 'retain-on-failure'` for full replay.
6. **Independent journeys** — each spec file can run in isolation. Auth
   state via `storageState` file, not shared browser context.
7. **No parallel execution** — journeys run serially. Prod has one
   verification dataset; parallel tests would create race conditions on
   the same entities.

## What This Does NOT Cover

- **Performance testing** — not measuring response times or load capacity.
- **Destructive operations** — not testing delete workflows (too risky on
  prod, and the teardown handles its own deletes).
- **MCP protocol testing** — MCP uses a different transport (streamable HTTP).
  Covered by the existing MCP health check in `release.sh`, not by Playwright.
- **Agent execution flow** — claim/submit/review lifecycle is an agent concern,
  not a UI concern. Tested via the existing Django test suite (1289 tests).
- **Console/vafi integration** — requires vafi pods running. Out of scope for
  vtf post-deploy verification.

## Implementation Sequence

1. **Scaffold** — Create directory structure, playwright.config.ts, helpers
2. **Seed/teardown** — global-setup.ts and global-teardown.ts with API client
3. **Journey 1 (auth)** — Get login working against target env
4. **Journey 6 (API health)** — Quick win, validates infra
5. **Journey 2 (navigation)** — Page load validation
6. **Journey 3 (project/kanban)** — Core flow, depends on seed data
7. **Journey 4 (task detail)** — Extends journey 3
8. **Journey 5 (admin)** — Needs non-staff user from seed

Total estimated journeys: 6 files, ~25-30 test cases.

## Decisions

1. **Verification user vs admin** — Use the real admin account for UI login.
   The point is verifying what a real user experiences. A dedicated
   `verify-viewer` (non-staff) is seeded for permission tests only, created
   in global-setup and deleted in teardown.

2. **Scheduling** — Deploy-only for now. Cron-based drift detection is a
   future enhancement — trivially added as a k8s CronJob since the test
   suite is env-var driven. Adding cron now would require the verification
   project to live permanently, adding complexity for a problem we don't
   have yet.

3. **Credential storage** — Env vars sourced from `.env.prod` in vtf-deploy
   (gitignored). Consistent with existing secrets in `prod.yaml`. If CI is
   added later, variables move to GitLab CI/CD secrets — the test suite
   doesn't change.
