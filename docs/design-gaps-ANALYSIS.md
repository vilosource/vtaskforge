# vtaskforge — Design Gaps Analysis

Status: Active (2026-03-19)

Identified gaps in the current design that need resolution before or during implementation.

## Gaps

### 1. Initiative & Phase Shape — Not Defined

We have a Task shape but no equivalent for Initiative or Phase. What fields do they carry?

**Questions:**
- Initiative: id, name, workspace_id, description, default review flags, status (active/completed/archived)?
- Phase: id, name, initiative_id, order/sequence, status?
- Do phases have their own review flag defaults that cascade to tasks?
- Does an initiative have an overall status derived from its phases, or independently set?

**Status:** Open

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

### 4. `file` Link Type Missing from Table

The task shape and CLI examples reference `file` links but the link types table in the design doc only lists 7 types. `file` is used but not formally defined.

**Resolution:** Add `file` to the link types table.

**Status:** Open (minor — just a doc fix)

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

### 9. Workspace Binding — Unclear

The hierarchy says initiatives are bound to workspaces, but vtf is separate from mykb. How does vtf know about mykb workspaces?

**Options:**
- `workspace_id` is just a string label in vtf — no API call to mykb, just a reference
- vtf queries mykb to validate workspace exists (coupling)
- Workspace concept is vtf-native, separate from mykb workspaces (duplication)

**Questions:**
- Is `workspace_id` just a tag/label for grouping initiatives?
- Should vtf validate that the workspace exists in mykb?
- What happens if a workspace is archived in mykb but has active initiatives in vtf?

**Status:** Open

---

### 10. `blocked` vs Dependency-Blocked Distinction

A task can be `blocked` (manually set status — "waiting on external thing") or unclaimable due to unresolved `depends_on` links (automatic — dependencies not done yet). These are different concepts.

**Questions:**
- Should dependency-blocked tasks show differently on the board than manually blocked?
- Is dependency-blocked a computed state (not a status) that overlays on `todo`?
- Should the API expose a `claimable` flag that accounts for both?

**Proposed resolution:**
- `blocked` remains a manual status (set by human or agent — "waiting on external dependency")
- Dependency-blocking is a **computed property** — task is in `todo` but has unresolved `depends_on` links, so it's not claimable. The API filters these out of the claimable pool. The board can show them as "waiting" within the Todo column.

**Status:** Open
