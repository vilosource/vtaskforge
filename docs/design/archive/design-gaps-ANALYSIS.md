# vtaskforge — Design Gaps Analysis

> **⚠️ ARCHIVED — Phase 0–2 historical reference only (archived 2026-05-31).**
> All six gaps below were Resolved during Milestones 0–7. This doc no longer
> directs new work; kept as a record of early design questions. For current
> direction see [`../../ROADMAP.md`](../../ROADMAP.md).

Status: Complete (Phase 0–2 reference; all gaps Resolved)

Identified gaps in the current design that need resolution before or during implementation.

## Gaps

### 1. ~~Workplan & Milestone Shape — Not Defined~~ (Resolved)

**Decided:**

- **Workplan**: id, name, description, status (active/completed/archived), owner, tags, target_date, default review flags. Completing last milestone auto-completes the workplan.
- **Milestone**: id, name, description, workplan_id, status (pending/active/completed), review flag overrides (null = inherit). Dependencies are a DAG via the link system — multiple milestones can be active simultaneously.
- **Links are universal** — workplans, milestones, and tasks can all be link sources. Added `jira` link type.
- **Review flag cascade**: task (explicit) > milestone default > workplan default.

Full shapes documented in vtaskforge-DESIGN.md under "Entity Shapes".

**Status:** Resolved

---

### 2. ~~Status Transitions — Not Formalized~~ (Resolved)

**Decided:** Full state machine defined and enforced by the API server.

- `done` and `cancelled` are terminal — no transitions out. Create a new task instead.
- `cancelled` and `deferred` are reachable from any non-terminal state.
- `changes_requested` routing uses `review_return_to` field (Option A) — stores which gate triggered the rejection so resubmit goes to the right place.
- API returns an error on invalid transitions.

Full state machine documented in vtaskforge-DESIGN.md under Review System Design.

**Status:** Resolved

---

### 3. ~~Concurrency — Two Agents Claiming Same Task~~ (Resolved)

**Decided: Atomic UPDATE with WHERE clause.** Same pattern as GitLab runner job claiming.

```sql
UPDATE tasks
SET status = 'doing', claimed_by = $agent_id, claimed_at = NOW()
WHERE id = $task_id
  AND status = 'todo'
  AND (assigned_to IS NULL OR assigned_to = $agent_id)
  AND (requires IS NULL OR requires <@ $agent_tags)
RETURNING id;
```

- Two agents race: one wins (200 OK), one loses (409 Conflict — "task already claimed")
- No locks needed — Postgres row-level MVCC handles it
- WHERE clause also enforces tag matching and pinned assignment

**Agent matching (three levels):**

| Level | Field | Meaning |
|---|---|---|
| Open | both null | Any agent can claim |
| Tagged | `requires: ["opus"]` | Only agents whose tags contain all required tags |
| Pinned | `assigned_to: "agent-id"` | Only this specific agent |

Agents register with tags (like GitLab runners): `["executor", "opus", "high-reasoning"]`.

**Status:** Resolved

---

### 4. ~~`file` Link Type Missing from Table~~ (Resolved)

Added `file` link type to the design doc table. `file` = Task → source file path, no execution constraint, context for agents.

**Status:** Resolved

---

### 5. ~~Kanban Columns Don't Match Statuses~~ (Resolved)

**Decided: 6 fixed columns (v1), badges for granularity within grouped columns.**

| Column | Statuses |
|--------|----------|
| Draft | `draft` |
| Review | `pending_start_review`, `pending_completion_review` (badge shows which gate) |
| Ready | `todo` (dependency-blocked shown with indicator) |
| In Progress | `doing` |
| Attention | `changes_requested`, `needs_attention`, `blocked` (badge shows specific status) |
| Done | `done` |

- `deferred` and `cancelled` hidden by default, visible via toggle
- Fixed columns for v1, customizable layout is a future concern
- One Review column (not split by gate type) — badge distinguishes, pile-up in one column signals bottleneck

**Status:** Resolved

---

### 6. ~~API Surface — Undefined~~ (Resolved)

**Decided: REST + OpenAPI + SSE.** Full API surface documented in [api-surface-DESIGN.md](api-surface-DESIGN.md).

Key decisions:
- REST with OpenAPI 3.x spec — codegen for Go (vf-agents) and TS (UIs)
- URL-based versioning (`/v1/`)
- SSE for real-time events with `Last-Event-ID` reconnection support
- Cursor-based pagination on all list endpoints
- Consistent error model with typed error codes
- Idempotency-Key header on all POST operations
- Task lifecycle actions as POST sub-resources (e.g., `/tasks/:id/claim`)
- Agent liveness via claim timeout + heartbeat (background expiry process)
- Bulk import endpoint for intake tooling
- Task notes as append-only comments (separate from reviews)
- Agent registration with tags and status tracking
- `?expand=links,reviews,events` for reducing round trips

**Status:** Resolved

---

### 7. ~~Event Types — Undefined~~ (Resolved)

**Decided:** Full event type list defined in [api-surface-DESIGN.md](api-surface-DESIGN.md) under the Event Stream section.

Event types cover: task lifecycle (created, updated, status_changed, claimed, unclaimed, completed, failed, blocked, unblocked, heartbeat), reviews (submitted), links (added, removed), workplans (created, updated, completed, archived), milestones (created, updated, activated, completed), agents (registered, deregistered, status_changed).

Key decisions:
- SSE format with event ID, type, and JSON data payload
- Consumers filter on subscription via query params (`?workplan=id&type=x`)
- `Last-Event-ID` header for reconnection replay (24h retention)
- Events are the same records stored in the `task_events` table — one source of truth

**Status:** Resolved

---

### 8. ~~Auth Model — Undefined~~ (Resolved)

**Decided: Django's pluggable auth system with DRF TokenAuthentication for v1.**

- V1: DRF `TokenAuthentication` — simple bearer tokens for all consumers (agents, humans, external systems)
- Each agent gets a token on registration, humans get tokens via Django admin or CLI
- Token maps to actor identity (actor_id, actor_type, actor_role)
- Passed as `Authorization: Bearer <token>` header

Future upgrades (just swap/add auth backends, no API changes):
- `SessionAuthentication` for web UI (cookie-based)
- `django-oauth-toolkit` for OAuth2
- Custom backend for short-lived agent JWT tokens

Django's auth is pluggable by design — adding backends doesn't touch the API or business logic.

**Status:** Resolved

---

### 9. ~~Workspace Binding — Unclear~~ (Resolved)

**Decided: No workspace binding. vtf stands alone.**

Workplans are standalone entities — no mandatory binding to mykb workspaces or any external system. External references (mykb workspace, Jira epic, wiki page) are optional links via the link system, not structural requirements.

This keeps vtf decoupled and usable without mykb. The link system already handles the real integration — tasks link to KB areas, docs, and external references as needed.

Removed `workspace_id` from hierarchy and CLI examples.

**Status:** Resolved

---

### 10. ~~`blocked` vs Dependency-Blocked Distinction~~ (Resolved)

**Decided: Two different concepts, handled differently.**

| Type | Source | Resolution | Status field |
|------|--------|-----------|-------------|
| **Dependency-blocked** | Internal — another task in vtf isn't done yet | Automatic — resolves when dependency completes | Not a status. Computed property on `todo` tasks. |
| **Manually blocked** | External — something outside the system | Manual — human/agent removes the block | `blocked` status |

- `blocked` = manual status for external dependencies ("waiting on client API keys", "infra team hasn't provisioned DB")
- Dependency-blocking = computed property. Task stays in `todo` but has unresolved `depends_on` links. API filters these out of the claimable pool. Board shows them in the Todo column with a "waiting on task X" indicator.
- API exposes a `claimable` flag on tasks that accounts for both status and dependency state.

**External block interface:** Manual blocks can also be resolved by external autonomous systems (CI pipelines, provisioning tools, other services). The API provides:
- `task.block` — sets `blocked` status with a reason and optional external reference (URL, ticket ID)
- `task.unblock` — any authenticated caller (human, agent, or external system) can unblock via API, with a resolution note
- V1: simple API endpoint. Future: webhook subscriptions, polling integrations.

**Status:** Resolved
