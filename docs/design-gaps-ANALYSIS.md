# vtaskforge — Design Gaps Analysis

Status: Active (2026-03-19)

Identified gaps in the current design that need resolution before or during implementation.

## Gaps

### 1. ~~Initiative & Phase Shape — Not Defined~~ (Resolved)

**Decided:**

- **Initiative**: id, name, description, status (active/completed/archived), owner, tags, target_date, default review flags. Completing last phase auto-completes the initiative.
- **Phase**: id, name, description, initiative_id, status (pending/active/completed), review flag overrides (null = inherit). Dependencies are a DAG via the link system — multiple phases can be active simultaneously.
- **Links are universal** — initiatives, phases, and tasks can all be link sources. Added `jira` link type.
- **Review flag cascade**: task (explicit) > phase default > initiative default.

Full shapes documented in vtaskforge-DESIGN.md under "Entity Shapes".

**Status:** Resolved

---

### 2. Status Transitions — Not Formalized

We list 11 task statuses but don't define which transitions are valid. Without a formal state machine, invalid transitions could occur.

**Questions:**
- Can a task go from `draft` directly to `todo` (skipping review)?
- Can `done` go back to `doing` (reopen)?
- Can `cancelled` be reversed?
- Who can trigger which transitions? (v1: anyone, but still need the valid set)
- Should the API server enforce valid transitions or just log warnings?

**Status:** Open

---

### 3. Concurrency — Two Agents Claiming Same Task

Two agents try to claim the same task simultaneously. The strategy needs to be decided.

**Options:**
- Postgres `SELECT FOR UPDATE` — row-level lock during claim
- Optimistic locking — version field, claim fails if version changed
- Advisory locks — Postgres advisory lock on task_id
- First-write-wins — unique constraint on (task_id, status=doing)

**Questions:**
- What does the losing agent see? Error? "Already claimed" response?
- Should the API return alternative available tasks when a claim fails?

**Status:** Open

---

### 4. ~~`file` Link Type Missing from Table~~ (Resolved)

Added `file` link type to the design doc table. `file` = Task → source file path, no execution constraint, context for agents.

**Status:** Resolved

---

### 5. Kanban Columns Don't Match Statuses

The kanban section shows 4 columns (`Todo | Doing | Blocked | Done`) but we now have 11 statuses. Need a mapping.

**Proposed column grouping:**

| Column | Statuses |
|--------|----------|
| Draft | draft |
| Review | pending_start_review, pending_completion_review |
| Todo | todo |
| In Progress | doing |
| Attention | changes_requested, needs_attention, blocked |
| Done | done |
| Hidden/Filtered | deferred, cancelled |

**Questions:**
- Is this the right grouping?
- Should users be able to customize column mappings?
- Should deferred/cancelled be visible with a toggle?

**Status:** Open

---

### 6. API Surface — Undefined

No RPC methods listed. The API is central to the architecture — every external system depends on it.

**Draft method list:**

```
# Initiatives
initiative.create
initiative.get
initiative.list
initiative.update
initiative.archive

# Phases
phase.create
phase.get
phase.list
phase.update
phase.reorder

# Tasks
task.create
task.get
task.list
task.update
task.claim
task.unclaim
task.complete
task.fail (needs_attention)

# Reviews
review.submit
review.list (per task)

# Links
link.add
link.remove
link.list

# Events
events.subscribe (SSE/WebSocket)

# Task Events (read-only)
task_events.list (per task)
task_events.query (across tasks — metrics)
```

**Questions:**
- RPC style: REST, JSON-RPC, gRPC, or tRPC?
- Pagination strategy for list endpoints?
- Filtering/query language for task lists?

**Status:** Open

---

### 7. Event Types — Undefined

The event stream is consumed by scrum master, UIs, and pool manager but no event types are specified.

**Draft event types:**

```
task.created
task.updated
task.status_changed
task.claimed
task.unclaimed
task.completed
task.needs_attention

review.submitted
review.approved
review.rejected
review.changes_requested

link.added
link.removed

initiative.created
initiative.updated
initiative.archived

phase.created
phase.updated
```

**Questions:**
- Event payload format? (full entity snapshot vs delta?)
- Do consumers filter by event type on subscription, or receive all?
- Event ordering guarantees?
- Replay/catch-up for consumers that reconnect?

**Status:** Open

---

### 8. Auth Model — Undefined

How do agents and humans authenticate with the API?

**Options:**
- API keys (simple, v1-friendly)
- JWT tokens (standard, supports claims/roles)
- mTLS (for agent-to-API, more complex)
- OAuth2 (for web UI, standard browser flow)

**Questions:**
- v1: just API keys for everything?
- How are agent identities provisioned? Manual key generation?
- Does the web UI use a different auth flow than CLI/agents?
- Is auth required for local-only deployments?

**Status:** Open

---

### 9. ~~Workspace Binding — Unclear~~ (Resolved)

**Decided: No workspace binding. vtf stands alone.**

Initiatives are standalone entities — no mandatory binding to mykb workspaces or any external system. External references (mykb workspace, Jira epic, wiki page) are optional links via the link system, not structural requirements.

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
