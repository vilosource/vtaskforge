# Entity Display Names — Findings Analysis

**Date:** 2026-04-03
**Status:** Analysis complete, key direction decided (API v2 + SDKs)

## Problem Statement

Every Django model in vtf has a `__str__()` method that returns a human-readable name (e.g., `Task.__str__()` returns the title, `Project.__str__()` returns the name). But this representation is lost at the serialization boundary — when models become JSON, related entity references are reduced to opaque nanoid strings.

The result: humans see `V1StGXR8_Z5jdHi6B-myT` where they should see "Platform Hardening". LLM agents receive bare IDs and must make follow-up API calls just to learn what an entity is called.

This is a systemic issue across all layers: REST API, Web UI, MCP tools, CLI, SSE events, and cross-service endpoints.

---

## Scope of Findings

| Layer | Opaque ID Fields | Files Affected |
|-------|-----------------|----------------|
| DRF Serializers | 23 fields across 10 serializers | 7 |
| Web UI (display) | 12+ places rendering bare IDs | ~15 |
| Web UI (extra fetches) | 3 redundant API calls per task page | 2 |
| MCP tool responses | 6 tools returning bare IDs | 5 |
| CLI output | 6 commands printing bare IDs | 2 |
| Cross-service (SSE, auth) | 3 endpoints missing names | 2 |

---

## Layer 1: DRF Serializers (the root cause)

All ForeignKey fields use DRF's default `PrimaryKeyRelatedField`, which serializes as a bare ID string. String-based ID fields (`claimed_by`, `created_by`, etc.) are plain `CharField` with no expansion.

### FK Fields Serialized as Bare IDs

| Serializer | Field | Target Model | Target `__str__()` |
|------------|-------|-------------|---------------------|
| TaskSerializer | `project` | Project | `.name` |
| TaskSerializer | `milestone` | Milestone | `.name` |
| TaskSerializer | `workplan` | Workplan | `.name` |
| WorkplanSerializer | `project` | Project | `.name` |
| MilestoneSerializer | `workplan` | Workplan | `.name` |
| ReviewSerializer | `task` | Task | `.title` |
| NoteSerializer | `task` | Task | `.title` |
| TaskEventSerializer | `task` | Task | `.title` |

**Source files:**
- `src/tasks/serializers.py:13-49` (TaskSerializer)
- `src/workplans/serializers.py:6-24` (WorkplanSerializer)
- `src/workplans/serializers.py:27-43` (MilestoneSerializer)
- `src/reviews/serializers.py:6-10` (ReviewSerializer)
- `src/tasks/serializers.py:6-10` (NoteSerializer)
- `src/events/serializers.py:6-10` (TaskEventSerializer)

### String ID Fields with No Display Resolution

| Serializer | Field | Refers To | Could Resolve To |
|------------|-------|-----------|-----------------|
| TaskSerializer | `claimed_by` | Agent ID | Agent.name |
| TaskSerializer | `assigned_to` | Agent/User ID | Agent.name or User.username |
| TaskSerializer | `created_by` | User/Agent ID | username |
| TaskSerializer | `requires` | List of Task IDs (JSONField) | List of {id, title} |
| ProjectSerializer | `owner` | User/Agent ID | username |
| ProjectSerializer | `created_by` | User/Agent ID | username |
| WorkplanSerializer | `owner` | User/Agent ID | username |
| WorkplanSerializer | `created_by` | User/Agent ID | username |
| MilestoneSerializer | `created_by` | User/Agent ID | username |
| ReviewSerializer | `reviewer_id` | Agent/User ID | Agent.name or username |
| NoteSerializer | `actor_id` | Agent/User ID | Agent.name or username |
| TaskEventSerializer | `triggered_by` | Agent/User ID | Agent.name or username |
| LinkSerializer | `created_by` | User/Agent ID | username |

**Source files:**
- `src/tasks/models.py:57-62` (claimed_by, assigned_to, created_by)
- `src/projects/serializers.py:6-22` (owner, created_by)
- `src/workplans/serializers.py:6-24` (owner, created_by)
- `src/reviews/serializers.py:6-10` (reviewer_id)
- `src/events/serializers.py:6-10` (triggered_by)

### Existing Positive Patterns (reference for fix)

| Serializer | Field | How It Works |
|------------|-------|-------------|
| AgentSerializer | `current_task` | SerializerMethodField returning `{id, title, status}` — **best example** |
| TaskSerializer | `claimed_by_pod_name` | SerializerMethodField doing Agent lookup — **partial expansion** |
| LinkSerializer | `source_title`, `target_title` | SerializerMethodField with per-row DB lookups — **N+1 anti-pattern** |
| TaskDetailSerializer | `links`, `reviews`, `events`, `traces` | Conditional expansion via `?expand=` query param |

**Source files:**
- `src/agents/serializers.py:35-39` (current_task — the gold standard)
- `src/tasks/serializers.py:51-59` (claimed_by_pod_name)
- `src/links/serializers.py:28-68` (source_title, target_title — N+1)

---

## Layer 2: Web UI — Bare IDs Displayed to Users

### IDs Rendered Directly in UI

| File | Line | What's Displayed | What User Sees |
|------|------|-----------------|----------------|
| `web/src/components/ConsoleWidget.tsx` | 109 | `target.project` | `Architect — V1StGXR8_Z5jdH...` |
| `web/src/components/MinimizedBar.tsx` | 11 | `target.project` | `Architect — V1StGXR8_Z5jdH...` |
| `web/src/components/TaskCard.tsx` | 62 | `task.claimed_by` | Nanoid of agent |
| `web/src/components/TaskCard.tsx` | 65 | `task.milestone` | Nanoid of milestone |
| `web/src/pages/TaskPage.tsx` | 184 | `noteObj.actor_id` | Nanoid of actor |
| `web/src/pages/TaskPage.tsx` | 242 | `task.claimed_by` | Nanoid of agent |
| `web/src/pages/TaskPage.tsx` | 246 | `task.assigned_to` | Nanoid of user/agent |
| `web/src/pages/TaskPage.tsx` | 251 | `task.requires.join(', ')` | Comma-separated nanoids |
| `web/src/pages/ProfilePage.tsx` | 96 | `p.project_id` | Nanoid of project |
| `web/src/pages/AdminLocksPage.tsx` | 75 | `lk.project_id` | Nanoid of project |
| `web/src/pages/AdminChannelMappingsPage.tsx` | 79 | `m.project_id` | Nanoid of project |

### Extra API Calls to Resolve IDs

The TaskPage and TaskDetail components make 3 separate queries to get names for the task's parent references:

```typescript
// web/src/pages/TaskPage.tsx:42-44
const { data: workplan } = useWorkplan(task?.workplan ?? '');
const { data: milestone } = useMilestone(task?.milestone ?? undefined);
const { data: project } = useProject(task?.project);
```

These are **3 round-trips** that would be unnecessary if the Task API response included `project_name`, `workplan_name`, and `milestone_name`.

### Console Widget Context

The `ConsoleUrlParams` type only carries IDs, no display names:

```typescript
// web/src/contexts/ConsoleWidgetContext.tsx:5-11
export interface ConsoleUrlParams {
  role?: string;
  project?: string;      // <-- nanoid, shown in title bar
  workplan?: string | number;  // <-- nanoid
  pod?: string;
  command?: string;
}
```

---

## Layer 3: MCP Tool Responses

### Tools Returning Bare Agent IDs

| Tool | Response Field | Current Value | Should Be |
|------|---------------|---------------|-----------|
| `vtf_board_overview` | `active_agents[].claimed_by` | Agent nanoid | Agent name |
| `vtf_task_detail` | `claimed_by` in task_info | Agent nanoid | Agent name |
| `vtf_search_tasks` | `task_list[].claimed_by` | Agent nanoid | Agent name |

**Source locations:**
- `src/tasks/services.py:412-418` — `active_agents` query returns `values("id", "claimed_by")`
- `src/mcp_server/tools/search.py:89` — `"claimed_by": task.claimed_by`
- `src/mcp_server/tools/detail.py:57-58` — `claimed_by` used in message without resolution

### Tools Returning Bare Project IDs

| Tool | Response Field | Current Value | Should Be |
|------|---------------|---------------|-----------|
| `vtf_whoami` | `projects[].project_id` | Project nanoid | + project_name |
| `vtf_manage_lock` (list) | `lock_data[].project_id` | Project nanoid | + project_name |
| `vtf_manage_channel_mapping` (list) | `mapping[].project_id` | Project nanoid | + project_name |

**Source locations:**
- `src/mcp_server/tools/identity.py:48-51` — whoami projects list
- `src/mcp_server/tools/identity.py:89-94` — lock list response

### Tools Accepting ID-Only Parameters (no name lookup)

| Tool | Parameter | Could Also Accept |
|------|-----------|-------------------|
| `vtf_manage_task` | `milestone_id` | Milestone name within workplan |
| `vtf_manage_task` | `workplan_id` | Workplan name within project |
| `vtf_manage_task` | `requires` | Comma-separated task titles or partial matches |

---

## Layer 4: CLI Output

### Commands Printing Bare IDs

| Command | Line | Output | Shows |
|---------|------|--------|-------|
| `vtf task show` | `cli/vtf/commands/task.py:70` | `Milestone: {id}` | Nanoid |
| `vtf task show` | `cli/vtf/commands/task.py:71` | `Workplan: {id}` | Nanoid |
| `vtf task show` | `cli/vtf/commands/task.py:72` | `Claimed by: {id}` | Nanoid |
| `vtf task show` | `cli/vtf/commands/task.py:73` | `Requires: {id}, {id}` | Nanoids joined |
| `vtf user show` | `cli/vtf/commands/user.py:74` | `{project_id} {role}` | Nanoid |
| `vtf lock list` | `cli/vtf/commands/user.py:185` | `{project_id}` column | Nanoid |
| `vtf channel-mapping list` | `cli/vtf/commands/user.py:235` | `{project_id}` column | Nanoid |

---

## Layer 5: Cross-Service Boundaries

### SSE Event Stream

The event stream enriches payloads with `task_id` but not `task_title`:

```python
# src/events/stream.py:79
enriched_data = {**event.data, "task_id": event.task_id}
```

Frontend consumers must make a separate query to resolve the task name from this event.

### Token Validation Endpoint

The cross-service identity endpoint returns project memberships as bare IDs:

```python
# src/prefs/views.py:102-104
projects = [
    {"project_id": m.project_id, "role": m.role}
    for m in memberships
]
```

Any consuming service (vtf-kb, vafi) that wants to display "user has access to Project X" must make another call to resolve the project name.

---

## Anti-Patterns Identified

### 1. N+1 in LinkSerializer

`source_title` and `target_title` each make a per-row database query:

```python
# src/links/serializers.py:28-47
def get_target_title(self, obj):
    if obj.target_type == "task":
        return Task.objects.values_list("title", flat=True).get(pk=obj.target_id)
    # ... same for milestone, workplan
```

With 10 links, this is 20 extra queries. Should use prefetching or batch resolution.

### 2. Partial Expansion (claimed_by_pod_name)

TaskSerializer resolves `claimed_by` to `pod_name` but not to `name`:

```python
# src/tasks/serializers.py:51-59
def get_claimed_by_pod_name(self, obj):
    agent = Agent.objects.get(id=obj.claimed_by)
    return agent.pod_name  # Why pod_name but not name?
```

This was added for the console widget's terminal connection. It demonstrates the expansion pattern but applies it inconsistently — the agent's `name` field (what humans want) is not included.

### 3. Frontend Compensating with Extra Fetches

TaskPage makes 3 extra API calls to resolve IDs to names. This is the frontend working around a backend data gap — the correct fix is to include names in the Task API response.

---

## Summary: All Opaque ID Fields

Total: **~50 fields** across the system where an entity reference is an opaque ID without a display name.

| Category | Count | Severity |
|----------|-------|----------|
| FK fields in serializers (no name) | 8 | High — causes frontend extra fetches |
| String ID fields in serializers (no resolution) | 13 | High — no way to resolve without extra call |
| Web UI displaying bare IDs | 11 | High — directly visible to users |
| MCP responses with bare IDs | 6 | Medium — LLM agents need extra calls |
| CLI output with bare IDs | 7 | Medium — visible to CLI users |
| Cross-service bare IDs | 3 | Medium — downstream services need extra calls |
| JSONField with bare ID lists (requires) | 1 | High — completely opaque to humans |

---

## What Works Well (keep these patterns)

1. **AgentSerializer.current_task** — `{id, title, status}` nested object. The ideal pattern.
2. **MCP search/detail tools** — Resolve `milestone` to `task.milestone.name`. Proves the approach works.
3. **TaskDetailSerializer ?expand=** — Conditional deep expansion. Good for optional heavy fields.
4. **ConsoleWidget title logic** — Already has the rendering code, just needs the data (`target.project` needs to carry the name).

---

## Consumer Audit

Five distinct consumers of the vtf API have been identified. Each has different needs for entity display names based on how they use entity references.

### Consumer 1: Web UI (React SPA)

**Role:** Primary human-facing interface. Full CRUD on all entities. Most sensitive to missing display names.

**How it calls vtf:** React Query hooks wrapping fetch calls to REST API endpoints.

**Data flow pattern:** Page loads → fetch entity by ID → need parent names for breadcrumbs, cards, detail views → make follow-up queries if names missing.

#### Per-Page Entity Reference Needs

| Page/Component | Primary Endpoint | Follow-up Queries | What's Missing |
|---------------|-----------------|-------------------|----------------|
| **TaskPage** | `GET /v1/tasks/{id}/?expand=...` | 3: useProject, useWorkplan, useMilestone | project_name, workplan_name, milestone_name on Task |
| **TaskDetail (modal)** | `GET /v1/tasks/{id}/?expand=...` | 3: useProject, useWorkplan, useMilestone | Same as TaskPage |
| **BoardView** | `GET /v1/tasks/?workplan={id}` | 3: useProject, useWorkplan, useMilestone (breadcrumbs) | Parent names for breadcrumb rendering |
| **WorkplanDetail** | `GET /v1/workplans/{id}/milestones/` | N: useMilestoneStats per milestone | Inline stats (total_tasks, by_status, completed_pct) per milestone |
| **ProjectDashboard** | `GET /v1/projects/{id}/workplans/` | 0 (stats already included) | None — good pattern |
| **KanbanBoard** | `GET /v1/tasks/?milestone={id}` | 0 for tasks | milestone_name on TaskCard badge |
| **AgentList** | `GET /v1/agents/` | 0 (current_task included) | None — good pattern |
| **ProfilePage** | `GET /v1/auth/validate/` | 0 | project_name in membership list |
| **AdminLocksPage** | `GET /v1/locks/` | 0 | project_name alongside project_id |
| **AdminChannelMappingsPage** | `GET /v1/channel-mappings/` | 0 | project_name alongside project_id |

#### UI Components Displaying Bare IDs

| Component | Field Displayed | What User Sees | What They Should See |
|-----------|----------------|---------------|---------------------|
| ConsoleWidget title bar | `target.project` | Nanoid | Project name |
| MinimizedBar label | `target.project` | Nanoid | Project name |
| TaskCard badge | `task.milestone` | Nanoid | Milestone name |
| TaskCard badge | `task.claimed_by` | Nanoid | Agent name |
| TaskPage assignment | `task.claimed_by` | Nanoid | Agent name |
| TaskPage assignment | `task.assigned_to` | Nanoid | Agent/user name |
| TaskPage dependencies | `task.requires.join()` | Nanoids | Task titles (linked) |
| TaskPage notes | `noteObj.actor_id` | Nanoid | Agent/user name |
| ProfilePage memberships | `p.project_id` | Nanoid | Project name |

#### Redundant API Calls (quantified)

| Scenario | Extra Queries | Per-Session Impact |
|----------|--------------|-------------------|
| Open a task detail page | 3 (project + workplan + milestone) | Most common action |
| Open task detail modal | 3 (same) | Second most common |
| Navigate to kanban board | 3 (breadcrumb names) | Every board navigation |
| View workplan with 10 milestones | 10 (one stats call per milestone) | Every workplan view |
| **Total per typical session** | **~20-30 extra round-trips** | |

#### TypeScript Contract Gap

Current types define entity references as bare strings:

```typescript
// web/src/api/tasks.ts
export interface Task {
  project: string;      // bare nanoid
  workplan: string;     // bare nanoid
  milestone: string;    // bare nanoid
  claimed_by: string;   // bare nanoid
  assigned_to: string;  // bare nanoid
  requires: string[];   // array of bare nanoids
}
```

#### SSE Event Handling

- Events contain only `task_id` — no `task_title`
- Every event triggers full query invalidation via `queryClient.invalidateQueries`
- Frontend refetches entire task lists instead of merging event data into cache
- Adding `task_title` and `task_status` to event payloads would enable direct cache updates

---

### Consumer 2: CLI (vtf command-line tool)

**Role:** Developer and operator interface. Used for task management, debugging, bulk operations. Needs readable output in terminal.

**How it calls vtf:** `VTFClient` (thin httpx wrapper) calling REST API endpoints. No shared ID resolution logic.

**Data flow pattern:** Command → single API call → format and print. No follow-up calls for name resolution.

#### Per-Command Entity Reference Needs

| Command | Endpoint | Bare IDs in Output | Name Data That Would Help |
|---------|----------|-------------------|--------------------------|
| `vtf task show` | `GET /v1/tasks/{id}/` | milestone, workplan, claimed_by, requires | All four need names |
| `vtf task list` | `GET /v1/tasks/` | Task IDs (truncated) | Already shows title — OK |
| `vtf task claim` | `POST /v1/tasks/{id}/claim/` | agent_id in confirmation | Agent name |
| `vtf task create` | `POST /v1/tasks/` | Created task ID | Response already has title — OK |
| `vtf milestone show` | `GET /v1/milestones/{id}/` | workplan field | workplan_name |
| `vtf user show` | `GET /v1/users/{id}/` | membership.project_id | project_name |
| `vtf lock list` | `GET /v1/locks/` | project_id column | project_name |
| `vtf channel-mapping list` | `GET /v1/channel-mappings/` | project_id column | project_name |

#### Input Parameter Observations

- All commands accept entity IDs only — no name-based lookup
- Exception: `vtf member add <project_id> <username>` accepts username (not user ID)
- Exception: `vtf user list --search <query>` does username search
- Import command makes one follow-up call: fetches workplan to infer project_id

#### CLI Consumer Needs Summary

The CLI makes **zero follow-up calls** for name resolution — it simply prints whatever the API returns. If the API includes `*_name` fields, the CLI output improves with no CLI code changes needed for most commands. Only the output formatting (`click.echo` lines) needs updating to prefer names over IDs.

---

### Consumer 3: MCP Tools (LLM Agent Interface)

**Role:** Machine-to-machine interface for Claude Code and vafi agents. Agents chain tool calls to accomplish tasks. Extra tool calls for name resolution waste tokens and latency.

**How it calls vtf:** Direct Django ORM queries and service function calls within the same process. Not HTTP — runs in-process.

**Data flow pattern:** Agent calls tool → tool queries ORM → formats response dict → returns JSON string. Agents chain outputs of one tool as inputs to the next.

#### Typical Agent Workflow Chain

```
1. vtf_whoami()
   Returns: {projects: [{project_id: "xY9...", role: "owner"}]}
   Gap: No project_name — agent doesn't know what "xY9..." is called

2. vtf_get_context(project_id="xY9...")
   Returns: {workplans: [{id: "aBc...", name: "Platform Hardening", status: "active"}]}
   Good: Workplan names included

3. vtf_search_tasks(workplan_id="aBc...")
   Returns: [{id: "tsk...", title: "Add auth", milestone: "Phase 1 Core", claimed_by: "zZz..."}]
   Partial: milestone resolved to name, but claimed_by is bare agent ID

4. vtf_task_detail(task_id="tsk...")
   Returns: {task info with reviews, notes, dependencies}
   Gap: claimed_by bare, workplan_name missing, project_name missing

5. vtf_manage_task(action="claim", task_id="tsk...", agent_id="zZz...")
   Input: Requires exact agent_id — no name-based lookup
```

#### Name Resolution Quality by Tool

| Tool | Project | Workplan | Milestone | Agent/User | Task Deps |
|------|---------|----------|-----------|------------|-----------|
| vtf_whoami | ID only | N/A | N/A | Self (username) | N/A |
| vtf_get_context | ID only | Name | N/A | N/A | N/A |
| vtf_search_tasks | N/A | Filter only | Name | ID only | N/A |
| vtf_task_detail | ID only | ID only | ID only | ID only | Title + status |
| vtf_board_overview | Filter only | Filter only | N/A | ID only | N/A |
| vtf_workplan_tree | N/A | Name | Name | N/A | Title |
| vtf_manage_task | ID input | ID input | ID input | ID input | N/A |
| vtf_manage_workplan | ID input | Name | N/A | N/A | N/A |
| vtf_manage_milestone | N/A | ID input | Name | N/A | N/A |
| vtf_plan_work | ID input | N/A | N/A | N/A | N/A |
| vtf_manage_lock | N/A | N/A | N/A | Username | N/A (project ID only) |

#### Agent Tool Call Overhead

Without name resolution in responses, agents make extra calls:
- `vtf_whoami` returns project_id → agent must call `vtf_get_context` just to learn project name
- `vtf_task_detail` returns bare workplan_id → agent must call `vtf_manage_workplan(action=list)` to find name
- `vtf_board_overview` returns bare `claimed_by` → no tool exists to resolve agent ID to name in a single call

Estimated overhead: **15-20% of tool calls are purely for name resolution** that could be eliminated by including names in responses.

---

### Consumer 4: vafi Controller (Autonomous Agent Executor)

**Role:** Kubernetes-based task executor. Claims tasks from vtf, runs Claude Code agents, reports results. Machine-to-machine — no human UI, but generates context for agents.

**How it calls vtf:** `httpx.AsyncClient` with token auth, calling REST API endpoints over HTTP within the cluster.

**Data flow pattern:** Poll claimable → claim task → fetch task detail with reviews → build context.md → invoke Claude Code agent → report results.

#### Entity References in vafi's Workflow

| Step | API Call | Entity Refs Used | Name Resolution |
|------|----------|-----------------|-----------------|
| Poll for work | `GET /v1/tasks/claimable/` | task_id, title | Title available |
| Claim task | `POST /v1/tasks/{id}/claim/` | task_id, agent_id | Agent self-known |
| Fetch context | `GET /v1/tasks/{id}/?expand=reviews` | task_id, project, workplan | project_id used to fetch repo URL |
| Get repo info | `GET /v1/projects/{id}/` | project_id | Gets repo_url, default_branch |
| Build context.md | In-memory | task title, spec, reviews | Reviews show reviewer_id (bare) |
| Post notes | `POST /v1/tasks/{id}/notes/` | task_id | Stores metadata as text |
| Complete/fail | `POST /v1/tasks/{id}/complete/` | task_id | N/A |

#### Context.md — What Agents See

The vafi controller materializes task context into `.vafi/context.md` for the Claude Code agent:

```markdown
# Task: Add auth endpoint (task-abc-123)

## Specification
...full spec text...

## Reviews
- changes_requested by reviewer-xyz-789: "Missing error handling"
```

**Gaps:**
- No project name in context header
- No workplan name in context header
- Reviewer shown as bare ID, not name
- Agent has no knowledge of where this task sits in the hierarchy

#### vafi Consumer Needs Summary

vafi is execution-focused — it doesn't render UI. But the context.md it generates is read by Claude Code agents, which benefit from understanding scope. Adding `project_name` and `workplan_name` to the Task API response would let vafi include them in context without extra API calls.

---

### Consumer 5: Cross-Service Boundaries

**Role:** Service-to-service communication: auth validation, SSE events, CXDB trace correlation.

#### 5a. Token Validation (`GET /v1/auth/validate/`)

**Consumers:** vafi bridge, future vtf-kb service, any external service validating tokens.

**Current response:**
```json
{
  "user_id": 1,
  "username": "agent-executor",
  "user_type": "agent",
  "is_staff": false,
  "projects": [
    {"project_id": "xY9kLm2Nq...", "role": "member"}
  ]
}
```

**What consumers do with it:**
- vafi bridge: checks `project_id in member_projects` for access control
- Display/logging: "Not a member of xY9kLm2Nq..." is unhelpful

**What they need:** `project_name` alongside `project_id` for readable error messages and logging.

#### 5b. SSE Event Stream (`GET /v1/events/stream/`)

**Consumer:** Web frontend (React useSSE hook).

**Current payload:**
```json
{"task_id": "tsk-abc-123", "from": "draft", "to": "todo"}
```

**What consumer does:** Invalidates React Query cache, triggers full refetch of task lists.

**What would help:** Including `task_title` and `task_status` would enable:
- Toast notifications: "Task 'Add auth endpoint' moved to todo" instead of refetch
- Direct cache merge instead of invalidation (reduces network traffic)
- Lower priority than other fixes since refetch works functionally

#### 5c. CXDB Trace Labeling

**Consumer:** Execution traces stored in CXDB for observability.

**How task IDs are used:** Label format `task:{task_id}` written to CXDB context.

**Reverse lookup:** `CxdbClient.find_context_by_task(task_id)` searches labels. No reverse lookup from CXDB to task name exists.

**Impact:** Low — trace correlation works by ID. Adding task_title to CXDB labels would improve readability in trace UIs but is not critical.

#### 5d. vafi Bridge (Session Recording and Locks)

**Consumer:** FastAPI service bridging human/agent sessions to vtf.

**Entity references:**
- Stores `project_id` in lock and session records
- Displays `project_id` in error messages and logs
- No project_name available from `GET /v1/auth/validate/`

**Impact:** Medium — better logging and error messages if project_name included in auth response.

---

## Cross-Consumer Entity Reference Matrix

Summary of what each consumer needs for each entity type:

| Entity Field | Web UI | CLI | MCP/Agents | vafi | Cross-service |
|-------------|--------|-----|------------|------|---------------|
| **Task.project** → name | Display (breadcrumb, detail) | `vtf task show` output | Context for planning | context.md header | N/A |
| **Task.workplan** → name | Display (breadcrumb, detail) | `vtf task show` output | Context for planning | context.md header | N/A |
| **Task.milestone** → name | Display (card badge, detail) | `vtf task show` output | Already resolved in search | N/A | N/A |
| **Task.claimed_by** → name | Display (card, detail, notes) | `vtf task show` output | Board overview context | Review display in context.md | N/A |
| **Task.assigned_to** → name | Display (detail) | N/A | N/A | N/A | N/A |
| **Task.created_by** → name | N/A | N/A | N/A | N/A | N/A |
| **Task.requires** → titles | Display (linked list) | `vtf task show` output | Already resolved in detail | N/A | N/A |
| **Note.actor_id** → name | Display (note author) | N/A | N/A | Review author in context | N/A |
| **Review.reviewer_id** → name | Display (review author) | N/A | N/A | Review author in context | N/A |
| **Workplan.project** → name | N/A (already on project page) | N/A | N/A | N/A | N/A |
| **Milestone.workplan** → name | N/A (already on workplan page) | `vtf milestone show` | N/A | N/A | N/A |
| **Membership.project_id** → name | ProfilePage, AdminPages | `vtf user show`, lock/channel lists | vtf_whoami | N/A | auth/validate response |
| **Event.task_id** → title | Toast notifications | N/A | N/A | N/A | SSE payload |

### Priority Ranking by Impact

| Field to Resolve | Consumers Affected | User-Facing | Machine-Facing | Priority |
|-----------------|-------------------|-------------|----------------|----------|
| Task → project_name | Web, CLI, MCP, vafi | Yes | Yes | **P1** |
| Task → workplan_name | Web, CLI, MCP, vafi | Yes | Yes | **P1** |
| Task → milestone_name | Web, CLI | Yes | Partially done | **P1** |
| Task → claimed_by_name | Web, CLI, MCP | Yes | Yes | **P1** |
| Task.requires → titles | Web, CLI | Yes | Already done in MCP | **P2** |
| Note.actor_id → name | Web, vafi | Yes | Yes | **P2** |
| Review.reviewer_id → name | Web, vafi | Yes | Yes | **P2** |
| Membership → project_name | Web, CLI, cross-service | Yes | Yes | **P2** |
| Event → task_title | Web (SSE) | Indirect | No | **P3** |
| Link.source/target → status | Web (DependencyChain) | Yes | No | **P3** |
| Milestone inline stats | Web (WorkplanDetail) | Yes (eliminates N+1) | No | **P2** |

---

## Architectural Analysis

### Why This Is Not a Serializer Bug

The obvious fix — add `project_name = CharField(source='project.name', read_only=True)` to every serializer — would address the symptom. But the root cause is a missing architectural layer: vtf has no **entity abstraction** between the REST API and its consumers.

Every consumer today does its own ad-hoc work:
- The React SPA has `useProject()`, `useWorkplan()`, `useMilestone()` hooks that individually fetch and cache entities — reimplementing a client-side ORM
- The CLI's `VTFClient` is a thin HTTP wrapper with zero domain knowledge
- vafi's `VtfClient` is another thin HTTP wrapper, independently written
- MCP tools query Django ORM directly, each tool formatting its own response dicts

Four consumers, three languages, zero shared entity model. Each consumer solves the same problem (navigating entity relationships) in its own way, with its own gaps.

### Design Principles Violated

**Single Responsibility Principle (SRP):** React page components are responsible for both fetching/resolving entity data AND rendering UI. `TaskPage.tsx` contains 3 `useQuery` hooks purely for name resolution — that's data access logic in a presentation component.

**Open/Closed Principle (OCP):** Adding a new field to the Task entity (e.g., `priority`) requires changes in every consumer: serializer, TypeScript interface, CLI formatting, MCP response dict, vafi context builder. The entity shape is not extensible without modifying consumers.

**Interface Segregation Principle (ISP):** Every consumer receives the same monolithic Task JSON blob regardless of need. The CLI showing `vtf task list` gets the full spec text. The SSE handler gets 30 fields when it needs 2. There is no way to request "just the display fields" vs "the full entity."

**Dependency Inversion Principle (DIP):** Consumers depend directly on the HTTP response shape — a low-level transport concern. When the API adds a field, consumers must update their type definitions. There is no abstraction between "what the transport returns" and "what the consumer works with."

**Don't Repeat Yourself (DRY):** The pattern of "fetch entity by ID, extract name" is reimplemented in every consumer:
- React: `useProject(task.project)` → `project.name`
- CLI: would need `client.get(f"/v1/projects/{t['project']}")` → `p['name']`
- MCP: `task.milestone.name if task.milestone else None`
- vafi: `client.get(f"/v1/projects/{task['project']}")` → `repo_url`

Same traversal logic, four implementations, four places to break.

### The Missing Layer: Entity SDKs

In well-designed systems, there is always an abstraction between the transport (HTTP/JSON) and the consumer application logic. This is the client SDK — it maps raw API responses to typed domain objects that consumers interact with.

```
┌─────────────────────────────────────────────┐
│              Domain Model (Django)           │
│  Project ─→ Workplan ─→ Milestone ─→ Task   │
│  Agent, Review, Note, Link, Event           │
│  __str__() returns human-readable name      │
└──────────────────┬──────────────────────────┘
                   │ serializes via
┌──────────────────▼──────────────────────────┐
│              REST API Layer                  │
│  DRF serializers with rich responses        │
│  Always includes {id, name} for FK refs     │
│  ?expand= for optional child collections    │
│  Write accepts bare IDs, read returns names │
└──────────────────┬──────────────────────────┘
                   │ consumed by
┌──────────────────▼──────────────────────────┐
│           Client SDK Layer                   │
│                                              │
│  vtf-sdk-python          vtf-sdk-ts          │
│  ┌────────────────┐      ┌────────────────┐  │
│  │ VtfClient       │      │ VtfClient       │  │
│  │ Project entity  │      │ Project entity  │  │
│  │ Workplan entity │      │ Workplan entity │  │
│  │ Task entity     │      │ Task entity     │  │
│  │ Agent entity    │      │ Agent entity    │  │
│  │                 │      │                 │  │
│  │ Lazy relations  │      │ Lazy relations  │  │
│  │ Identity cache  │      │ React Query     │  │
│  │ Typed mutations │      │ Typed mutations │  │
│  └────────────────┘      └────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ used by
┌──────────────────▼──────────────────────────┐
│            Application Layer                 │
│                                              │
│  Web UI          CLI        MCP      vafi    │
│  (React SPA)     (Click)    (tools)  (ctrl)  │
│                                              │
│  Works with entity objects, never raw JSON.  │
│  task.project.name — always available.       │
│  task.workplan.milestones — lazy loaded.     │
│  task.claim(agent) — typed mutation.         │
└──────────────────────────────────────────────┘
```

### Entity Object Design

An entity object is not a data class — it is a **self-describing reference** that preserves `__str__()` across the serialization boundary.

**Scalar references (always eager):**

Every FK reference carries its display identity. These are populated from the API response at zero cost (the API includes them via `select_related`):

```python
# Python SDK
class EntityRef:
    """Lightweight reference to a related entity."""
    id: str
    name: str

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r}, name={self.name!r})"


class Task:
    id: str
    title: str
    status: str
    project: EntityRef      # always has .id and .name
    workplan: EntityRef     # always has .id and .name
    milestone: EntityRef    # always has .id and .name
    claimed_by: EntityRef   # always has .id and .name (agent)

    def __str__(self) -> str:
        return self.title
```

```typescript
// TypeScript SDK
interface EntityRef {
  readonly id: string;
  readonly name: string;
}

interface Task {
  readonly id: string;
  readonly title: string;
  readonly status: TaskStatus;
  readonly project: EntityRef;
  readonly workplan: EntityRef | null;
  readonly milestone: EntityRef | null;
  readonly claimedBy: EntityRef | null;
}
```

**Collection references (always lazy):**

Child collections are never included by default. They are fetched on first access and cached:

```python
# Python SDK
class Workplan:
    id: str
    name: str
    project: EntityRef

    @cached_property
    def milestones(self) -> list[Milestone]:
        """Fetched on first access, cached thereafter."""
        return self._client.list_milestones(workplan_id=self.id)

    @cached_property
    def tasks(self) -> list[Task]:
        return self._client.list_tasks(workplan_id=self.id)
```

```typescript
// TypeScript SDK — integrates with React Query
function useWorkplanMilestones(workplanId: string) {
  return useQuery({
    queryKey: ['workplan', workplanId, 'milestones'],
    queryFn: () => vtf.milestones.list({ workplanId }),
    enabled: !!workplanId,
  });
}
```

**Mutations (typed, return updated entities):**

```python
# Python SDK
task = vtf.tasks.get(task_id)
task = vtf.tasks.claim(task.id, agent_id=agent.id)
# Returns updated Task entity with all display names populated
print(f"Claimed '{task.title}' in {task.workplan.name}")
```

### Read vs Write Asymmetry

The API serves different shapes for reading and writing. This is the CQRS-lite pattern — not full event sourcing, but separate contracts for input and output:

| Direction | Entity References | Example |
|-----------|------------------|---------|
| **Read (GET response, POST/PATCH response)** | Rich: `{id, name}` objects | `"project": {"id": "xY9...", "name": "Auth System"}` |
| **Write (POST/PATCH body)** | Lean: bare ID strings | `"project": "xY9..."` |

This is not a special vtf pattern — it's how every well-designed REST API works. Stripe returns full customer objects in charge responses but accepts `customer: "cus_123"` on creation. GitHub returns full user objects in PR responses but accepts login strings for assignment.

The SDK encodes this asymmetry:
- Entity properties are read-only — you cannot set `task.project.name`
- Mutations accept IDs or entities — `vtf.tasks.create(project=project)` or `vtf.tasks.create(project_id="xY9...")`
- Responses always return full entity objects with display names

### What Changes at Each Layer

**API Layer (DRF serializers):**
- FK fields include `*_name` read-only companion fields
- String ID fields (claimed_by, reviewer_id, etc.) include `*_name` companions
- `?expand=` pattern for optional child collections
- Responses are identical for all consumers — the SDK adapts, not the API

**Python SDK (`vtf-sdk-python`):**
- Shared by CLI, MCP tools, vafi controller, future vtf-kb
- Replaces `cli/vtf/client.py` and vafi's `VtfClient`
- Entity objects with `EntityRef` for FK fields, `cached_property` for collections
- Auth handling (token, session) built into client
- Published as internal package or git submodule

**TypeScript SDK (`vtf-sdk-ts`):**
- Used by React SPA
- Replaces ad-hoc `api/*.ts` fetch functions
- Entity types with `EntityRef` for FK fields
- React Query integration via hooks
- Eliminates manual `useProject(task.project)` follow-up queries

**Consumers (application code):**
- Work exclusively with entity objects
- Never parse raw JSON responses
- Never construct URLs or manage auth
- `task.project.name` is always available — no conditional access, no fallbacks

### What This Enables

Beyond fixing the display name problem, the SDK layer enables:

1. **Consistent error handling** — SDK raises typed exceptions (`TaskNotFound`, `ClaimConflict`), consumers handle domain errors not HTTP status codes.

2. **API versioning** — If the API response shape changes, only the SDK adapts. Consumers are insulated.

3. **Testing** — Consumers can mock the SDK instead of HTTP responses. `MockVtfClient` returns entity objects, not JSON dicts.

4. **Documentation by types** — The SDK's type definitions are the API documentation. TypeScript types and Python type hints are always in sync with the API.

5. **Open source adoption** — A published SDK with typed entities is what makes an API adoptable. `pip install vtf-sdk` or `npm install @vtf/sdk` is the difference between "read the API docs" and "import and use."

### Relationship to Existing Patterns

vtf already has fragments of this architecture:

| Existing Pattern | Where | SDK Equivalent |
|-----------------|-------|---------------|
| `AgentSerializer.current_task` returns `{id, title, status}` | `src/agents/serializers.py:35-39` | EntityRef pattern |
| `TaskDetailSerializer ?expand=` | `src/tasks/serializers.py:139-182` | Lazy collection loading |
| `useProject()`, `useWorkplan()` React hooks | `web/src/hooks/` | SDK entity resolution |
| vafi `VtfClient` with typed methods | `~/GitHub/vafi/` | Python SDK client |
| `claimed_by_pod_name` SerializerMethodField | `src/tasks/serializers.py:51-59` | EntityRef enrichment |

The SDK formalizes and unifies these ad-hoc patterns into a consistent architecture.

---

## Case Study: GitLab API and python-gitlab SDK

GitLab's REST API is a mature, well-documented example of the exact pattern vtf needs. It solves the entity display name problem through **embedded entity summaries** — a fixed projection of related entities inlined in every response.

### The Embedded Summary Pattern

When you `GET /projects/:id/merge_requests/:iid`, GitLab does not return `"author": 87381`. It returns:

```json
{
  "id": 182390,
  "title": "Fix pipeline timeout handling",
  "state": "merged",
  "author": {
    "id": 87381,
    "username": "jdoe",
    "name": "Jane Doe",
    "state": "active",
    "avatar_url": "https://...",
    "web_url": "https://gitlab.com/jdoe"
  },
  "assignee": {
    "id": 12345,
    "username": "reviewer1",
    "name": "Bob Smith",
    "state": "active",
    "avatar_url": "https://...",
    "web_url": "https://gitlab.com/reviewer1"
  },
  "milestone": {
    "id": 4599664,
    "iid": 106,
    "title": "17.7",
    "state": "closed",
    "due_date": "2024-12-13",
    "web_url": "https://gitlab.com/groups/gitlab-org/-/milestones/106"
  },
  "references": {
    "short": "!182390",
    "relative": "!182390",
    "full": "gitlab-org/gitlab!182390"
  }
}
```

Every entity reference is a **self-describing object** — it carries enough context to display meaningfully without a follow-up API call.

### Read vs Write Naming Convention

GitLab uses a strict naming convention to distinguish read-side objects from write-side IDs:

| Direction | Field Name | Value |
|-----------|-----------|-------|
| Read (GET response) | `author` | `{id, username, name, avatar_url, web_url}` |
| Read (GET response) | `milestone` | `{id, title, state, due_date, web_url}` |
| Write (POST/PUT body) | `assignee_id` | `12345` (bare integer) |
| Write (POST/PUT body) | `milestone_id` | `4599664` (bare integer) |

The convention: **no suffix = rich read object**, **`_id` suffix = write-side bare reference**. This is the same pattern every consumer instinctively expects.

### Fixed Projection Contract

The embedded summary shape is **fixed per entity type**. A "user summary" always contains `{id, username, name, state, avatar_url, web_url}` — whether it appears as an MR author, an issue assignee, or a reviewer. This is a contract that consumers can depend on.

This matters for vtf: if we define that a "Project summary" is always `{id, name}` and a "Milestone summary" is always `{id, name, status}`, then consumers get a stable type to code against, regardless of which parent entity contains the reference.

### python-gitlab SDK

The python-gitlab SDK wraps API responses as `RESTObject` instances with `__getattr__` delegation to the response dict:

```python
project = gl.projects.get(278964)

# Embedded summaries are plain dicts — not lazy-loaded objects
mr = project.mergerequests.get(1)
mr.author["name"]       # "Jane Doe" — immediate, no API call
mr.milestone["title"]   # "17.7" — immediate, no API call

# Collections use Manager objects with lazy evaluation
type(project.mergerequests)  # ProjectMergeRequestManager — no HTTP call yet
mrs = project.mergerequests.list(per_page=20)  # triggers GET /projects/278964/merge_requests

# Navigation from summary to full object requires explicit call
full_user = gl.users.get(mr.author["id"])  # separate call if you need more than summary
```

Key design decisions:
- **Embedded summaries are plain dicts**, not navigable entity objects — simple and predictable
- **Collections are lazy** — the Manager object exists immediately, `.list()` fetches
- **No automatic deep loading** — if you need more than the summary, you ask explicitly
- **Write operations accept bare IDs** — `project.mergerequests.create({'source_branch': ..., 'assignee_id': 12345})`

### Lessons for vtf

| GitLab Pattern | vtf Current State | vtf Target State |
|---------------|-------------------|------------------|
| Embedded user summary `{id, name, username}` | Bare string ID `"claimed_by": "xY9..."` | `"claimed_by": {"id": "xY9...", "name": "executor-1"}` |
| Embedded milestone summary `{id, title, state}` | Bare FK ID `"milestone": "aBc..."` | `"milestone": {"id": "aBc...", "name": "Phase 1 Core"}` |
| `assignee_id` on write vs `assignee` on read | Same field name for both directions | `"project"` on read = `{id, name}`, `"project"` on write = bare ID (DRF handles this) |
| Fixed summary shape per entity type | No summary types defined | `ProjectRef`, `WorkplanRef`, `MilestoneRef`, `AgentRef` |
| Manager objects for lazy collections | Ad-hoc `useQuery` hooks / no pattern | SDK entity objects with lazy `.milestones`, `.tasks` |
| Plain dicts for summaries in SDK | N/A (no SDK exists) | `EntityRef` dataclass/interface in SDK |

### What vtf Should NOT Copy from GitLab

1. **python-gitlab uses plain dicts for summaries** — vtf SDK should use typed dataclasses/interfaces instead. GitLab's SDK predates modern Python typing; vtf can do better.

2. **GitLab's `RESTObject.__getattr__` magic** — Dynamic attribute access from a dict is convenient but makes IDE autocompletion and type checking impossible. vtf SDK should use explicit typed properties.

3. **No validation on summary shapes** — python-gitlab trusts whatever the API returns. vtf SDK should validate that summaries contain the expected fields (fail fast on contract violations).

### What vtf SHOULD Copy from GitLab

1. **Server-side join, always** — The API server resolves references. Consumers never chase IDs.
2. **Fixed summary shapes per entity type** — One canonical definition of what a "Project summary" contains.
3. **Naming convention for read vs write** — Clear distinction between rich read objects and lean write IDs.
4. **Lazy collections via explicit call** — Don't eager-load child entities. Provide a mechanism to fetch them on demand.
5. **Summary contains enough for display** — At minimum `{id, name/title}`. Optionally `status`, `web_url`, or other frequently-needed display fields.

---

## Key Decision: API Versioning (`/v2/`)

### The Problem with Incremental Fixes

Three options were considered for evolving the API:

| Option | Approach | Risk |
|--------|----------|------|
| **A: Add `*_name` sibling fields** | `"project": "xY9...", "project_name": "Auth System"` | Permanent legacy shape. SDK must merge two fields into one concept. Technical debt from day one. |
| **B: Change FK fields to objects** | `"project": {"id": "xY9...", "name": "Auth System"}` | Breaking change. All consumers must update simultaneously or things break. |
| **C: API versioning (`/v2/`)** | `/v1/` unchanged, `/v2/` with embedded summaries | Clean separation. No breaking changes. Consumers migrate independently. |

### Decision: Option C — Introduce `/v2/` with Embedded Entity Summaries

**Rationale:**
- `/v1/` stays exactly as-is — zero risk to current consumers
- `/v2/` is designed from scratch with the GitLab-style embedded summary pattern
- SDKs (`vtf-sdk-python`, `vtf-sdk-ts`) target `/v2/` exclusively
- Each consumer migrates from raw `/v1/` to SDK + `/v2/` independently, at its own pace
- Once all consumers are on `/v2/`, `/v1/` gets a deprecation notice, then eventual removal
- API versioning is a textbook architecture topic — vtf demonstrates it properly

### What `/v2/` Looks Like

**Entity references become embedded summary objects:**

```json
// v1 (current — stays unchanged)
{
  "id": "tsk-abc-123",
  "title": "Add auth endpoint",
  "project": "xY9kLm2Nq_pRs3tUvWz",
  "workplan": "aBcDeFgHiJkLmNoPqRs",
  "milestone": "zZzYyYxXwWvVuUtTsSr",
  "claimed_by": "agt-executor-001",
  "requires": ["tsk-def-456", "tsk-ghi-789"]
}

// v2 (new — designed for SDKs)
{
  "id": "tsk-abc-123",
  "title": "Add auth endpoint",
  "project": {"id": "xY9kLm2Nq_pRs3tUvWz", "name": "Auth System"},
  "workplan": {"id": "aBcDeFgHiJkLmNoPqRs", "name": "Platform Hardening"},
  "milestone": {"id": "zZzYyYxXwWvVuUtTsSr", "name": "Phase 1 Core"},
  "claimed_by": {"id": "agt-executor-001", "name": "executor-1"},
  "requires": [
    {"id": "tsk-def-456", "title": "Create user model"},
    {"id": "tsk-ghi-789", "title": "Add login endpoint"}
  ]
}
```

**Writes still accept bare IDs (both versions):**

```json
// POST /v2/tasks/  — write payload unchanged
{
  "title": "Add auth endpoint",
  "project": "xY9kLm2Nq_pRs3tUvWz",
  "workplan": "aBcDeFgHiJkLmNoPqRs",
  "milestone": "zZzYyYxXwWvVuUtTsSr"
}
```

DRF handles this naturally — `PrimaryKeyRelatedField` accepts an ID on write, and a custom `to_representation()` returns the embedded object on read.

### Fixed Summary Types (the Contract)

Each entity type has one canonical summary shape, used everywhere it appears as a reference:

| Entity | Summary Fields | Used When Referenced By |
|--------|---------------|----------------------|
| **ProjectRef** | `{id, name}` | Task, Workplan, Membership, Lock, ChannelMapping |
| **WorkplanRef** | `{id, name}` | Task, Milestone |
| **MilestoneRef** | `{id, name, status}` | Task |
| **AgentRef** | `{id, name}` | Task (claimed_by, assigned_to), Review (reviewer), Note (actor), Event (triggered_by) |
| **TaskRef** | `{id, title, status}` | Task (requires), Link (source/target), Agent (current_task) |

These are the building blocks. The SDKs define corresponding types (`EntityRef` base, with typed variants per entity).

### Implementation Sequence

Each step must be right before the next one builds on it. Each step is independently valuable — if we stop at any point, the system is in a better state than before.

```
Step 1: Define summary types and v2 serializers
        (DRF, no consumer changes, v1 untouched)
              │
Step 2: Build vtf-sdk-python
        (Entity objects, EntityRef, lazy collections)
        (Targets /v2/ endpoints)
              │
Step 3: Build vtf-sdk-ts  
        (TypeScript entity types, React Query integration)
        (Targets /v2/ endpoints)
              │
Step 4: Migrate consumers one at a time
        4a: CLI → vtf-sdk-python
        4b: vafi controller → vtf-sdk-python
        4c: React SPA → vtf-sdk-ts
        4d: MCP tools → vtf-sdk-python (or keep ORM — design decision)
              │
Step 5: Deprecate /v1/
        (Once all consumers confirmed on /v2/)
              │
Step 6: Remove /v1/
        (Clean break)
```

### Open Questions (for future design doc)

These need answers before implementation begins:

1. **Versioning mechanism** — URL prefix (`/v2/tasks/`) vs header (`Accept: application/vnd.vtf.v2+json`) vs query param (`?version=2`). URL prefix is simplest and most visible.

2. **Shared vs separate serializers** — Do v1 and v2 share a base serializer with different `to_representation()`? Or are they completely separate classes? Shared base avoids drift but adds coupling.

3. **MCP tools and /v2/** — MCP tools currently use Django ORM directly (in-process). Should they switch to the Python SDK (which calls HTTP), or should they use v2 serializers directly? In-process ORM is faster but bypasses the SDK abstraction.

4. **SDK packaging** — Monorepo subfolder, separate repos, or published packages? For internal use, monorepo subfolder is simplest. For open source, published packages (`pip install vtf-sdk`, `npm install @vtf/sdk`).

5. **Migration testing** — How to verify that a consumer works correctly on /v2/ before cutting over? Shadow traffic? Feature flags? Parallel runs?

6. **Summary field selection** — Which fields belong in each summary type? Minimal (`{id, name}`) or richer (`{id, name, status, web_url}`)? The GitLab case study suggests richer summaries reduce follow-up calls, but they also increase payload size and staleness risk.

---

## SDK Design Vision: Resource-Oriented Object Model

The SDKs should present vtf's domain as **navigable objects**, not HTTP plumbing. This is the pattern used by Stripe, AWS boto3, GitHub's Octokit, and Django's own ORM. The consumer thinks in domain terms — projects, workplans, milestones, tasks — and the SDK maps that to API calls transparently.

### The Developer Experience We're Targeting

**Python SDK:**

```python
from vtf_sdk import VtfClient

vtf = VtfClient(url="https://vtf.example.com", token="...")

# ── Navigate the hierarchy ──────────────────────────────
project = vtf.projects.get("xY9...")
print(project.name)                       # "Auth System"
print(project.status)                     # "active"

for wp in project.workplans:              # lazy — fetches on first access
    print(wp.name)                        # "Platform Hardening"
    for ms in wp.milestones:              # lazy
        print(f"  {ms.name}: {ms.status}")
        for task in ms.tasks:             # lazy
            print(f"    {task.title} [{task.status}]")

# ── References are always self-describing ────────────────
task = vtf.tasks.get("tsk-abc")
print(task.project.name)                  # "Auth System" — no extra call
print(task.workplan.name)                 # "Platform Hardening" — no extra call
print(task.milestone.name)                # "Phase 1 Core" — no extra call
print(task.claimed_by.name)              # "executor-1" — no extra call

for dep in task.requires:                 # list of TaskRef objects
    print(f"  depends on: {dep.title}")   # not a nanoid

# ── Actions are methods on the resource ──────────────────
task = vtf.tasks.claim(task.id, agent_id=agent.id)
print(f"Claimed '{task.title}' on {task.project.name}")

task.add_note("All tests passing, ready for review")
task.complete()

# ── Filtering through managers ───────────────────────────
doing = vtf.tasks.list(status="doing", project=project.id)
for t in doing:
    print(f"{t.title} — claimed by {t.claimed_by.name}")

claimable = vtf.tasks.claimable(tags=["executor"])
for t in claimable:
    print(f"{t.title} in {t.workplan.name}")

# ── Create with bare IDs or entity objects ───────────────
new_task = vtf.tasks.create(
    title="Add logout endpoint",
    project=project,             # accepts entity object
    workplan=wp,                 # or bare ID string
    milestone=ms,
)
```

**TypeScript SDK:**

```typescript
import { VtfClient } from '@vtf/sdk';

const vtf = new VtfClient({ url: 'https://vtf.example.com', token: '...' });

// ── Direct entity access ────────────────────────────────
const task = await vtf.tasks.get('tsk-abc');
task.project.name;                        // "Auth System"
task.milestone?.name;                     // "Phase 1 Core"
task.claimedBy?.name;                     // "executor-1"
task.requires.map(t => t.title);          // ["Create user model", "Add login endpoint"]

// ── Lazy collections ────────────────────────────────────
const project = await vtf.projects.get('xY9...');
const workplans = await project.workplans.list();
const milestones = await workplans[0].milestones.list();

// ── Actions ─────────────────────────────────────────────
const claimed = await vtf.tasks.claim(task.id, { agentId: agent.id });
await vtf.tasks.complete(task.id);

// ── React integration via hooks ─────────────────────────
// The SDK provides React Query-aware hooks
function TaskHeader({ taskId }: { taskId: string }) {
  const { data: task } = useTask(taskId);

  return (
    <Breadcrumb segments={[
      { label: task.project.name, to: `/projects/${task.project.id}` },
      { label: task.workplan.name, to: `/projects/${task.project.id}/workplans/${task.workplan.id}` },
      { label: task.milestone.name },
    ]} />
  );
  // Zero follow-up queries. Everything came with the task.
}
```

### Design Principles Behind the SDK

**1. Resources are objects, not dicts**

Every API entity maps to a typed class with properties and methods. The consumer never indexes into a dict or checks if a key exists.

```python
# Today (raw JSON)
name = task_dict.get("project", {}).get("name", "unknown")  # defensive, ugly

# With SDK
name = task.project.name  # typed, guaranteed by contract, IDE autocompletes
```

**2. References are always self-describing**

No bare IDs in the object model. Every reference is an `EntityRef` (or typed subclass) with at minimum `.id` and `.name`. This is the `__str__()` surviving serialization.

```python
class EntityRef:
    """Base reference to a related entity. Always has id and name."""
    id: str
    name: str

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        return isinstance(other, EntityRef) and self.id == other.id

class ProjectRef(EntityRef):
    """Reference to a Project. Carried by Task, Workplan, Membership."""
    pass

class AgentRef(EntityRef):
    """Reference to an Agent. Carried by Task (claimed_by, assigned_to)."""
    pass

class TaskRef(EntityRef):
    """Reference to a Task. Carried by requires, Link, Agent.current_task."""
    title: str  # tasks use 'title' not 'name'
    status: str

    @property
    def name(self) -> str:
        return self.title  # EntityRef contract satisfied
```

**3. Collections are lazy, accessed through managers**

Child collections are never fetched until asked. Managers provide `.list()`, `.get()`, and filtering:

```python
class Workplan:
    id: str
    name: str
    project: ProjectRef

    @cached_property
    def milestones(self) -> MilestoneManager:
        """Manager for this workplan's milestones. Fetches on .list() or iteration."""
        return MilestoneManager(client=self._client, workplan_id=self.id)

class MilestoneManager:
    def list(self, **filters) -> list[Milestone]:
        return self._client._get(f"/v2/workplans/{self._workplan_id}/milestones/", params=filters)

    def get(self, id: str) -> Milestone:
        return self._client._get(f"/v2/milestones/{id}/")

    def __iter__(self):
        """Enables: for ms in workplan.milestones: ..."""
        return iter(self.list())
```

**4. Mutations return updated entities**

Every write operation returns the updated entity with all display names populated. The consumer always has current state:

```python
task = vtf.tasks.claim(task_id, agent_id=agent.id)
# task is a full Task object with:
#   task.status == "doing"
#   task.claimed_by.name == "executor-1"
#   task.project.name == "Auth System"
# No follow-up query needed.
```

**5. Write accepts IDs or entities (duck typing)**

Create/update methods accept either bare ID strings or entity objects for FK references. The SDK extracts the ID transparently:

```python
# Both work:
vtf.tasks.create(title="...", project="xY9...")          # bare ID
vtf.tasks.create(title="...", project=project)            # entity object

# SDK internally does:
def _resolve_id(value):
    if isinstance(value, EntityRef):
        return value.id
    return value  # assume it's already an ID string
```

**6. Errors are domain-specific, not HTTP-specific**

```python
from vtf_sdk.exceptions import TaskNotFound, ClaimConflict, GuardViolation

try:
    vtf.tasks.claim(task_id, agent_id=agent.id)
except ClaimConflict as e:
    print(f"Already claimed by {e.held_by}")      # typed exception with context
except GuardViolation as e:
    print(f"Guard failed: {e.guard_name}")
except TaskNotFound:
    print("Task does not exist")

# Not this:
# except requests.HTTPError as e:
#     if e.response.status_code == 409: ...
```

### How This Maps to the Architecture Layers

```
Consumer code sees:     task.project.name
                           │
SDK translates to:      Task(project=ProjectRef(id="xY9...", name="Auth System"))
                           │
Built from API:         GET /v2/tasks/tsk-abc → {"project": {"id": "xY9...", "name": "Auth System"}}
                           │
Server resolves via:    select_related('project') + v2 serializer to_representation()
                           │
Database stores:        tasks.project_id = "xY9..." (FK to projects.id)
```

Each layer has one job:
- **Database**: stores the FK relationship
- **Django ORM**: resolves it via `select_related()`
- **v2 serializer**: formats it as `{id, name}` in JSON
- **SDK**: wraps it as a typed `ProjectRef` object
- **Consumer**: accesses `.name` — never thinks about IDs

### Comparison: Today vs Target

| Aspect | Today | Target |
|--------|-------|--------|
| Get a task's project name | `useProject(task.project)` → 2nd API call → `project.name` | `task.project.name` |
| Display claimed agent | `task.claimed_by` → shows nanoid | `task.claimed_by.name` → shows "executor-1" |
| List task dependencies | `task.requires.join(', ')` → nanoid soup | `task.requires.map(t => t.title)` → readable titles |
| Create a task | `fetch('/v1/tasks/', {body: {project: id, ...}})` | `vtf.tasks.create(project=project, ...)` |
| Handle claim conflict | `if (response.status === 409) ...` | `catch ClaimConflict as e: e.held_by` |
| Traverse hierarchy | 3 separate hooks + 3 API calls | `task.project.name`, `task.workplan.milestones` |
| Test consumer code | Mock HTTP responses (JSON dicts) | Mock SDK (`MockVtfClient` returning entity objects) |

### SDK Reference Implementations to Study

| SDK | Language | Pattern Worth Studying |
|-----|----------|----------------------|
| **Stripe** | Python, Node, Go | Resource objects with methods (`customer.subscriptions.list()`), typed exceptions, idempotency keys |
| **boto3 (AWS)** | Python | Resource vs Client layer (high-level objects vs low-level API calls), lazy collections with paginators |
| **python-gitlab** | Python | Manager pattern (`project.mergerequests`), `RESTObject` base class, dict-backed attributes |
| **Octokit (GitHub)** | TypeScript | Typed responses, plugin architecture, pagination helpers |
| **Django ORM** | Python | `select_related()` / `prefetch_related()`, lazy querysets, manager pattern — the gold standard for Python ORMs |
| **Prisma** | TypeScript | Generated typed client from schema, `include` for relations, type-safe filtering |

The vtf SDK doesn't need to be as sophisticated as any of these. The key patterns to adopt are: **typed entity objects**, **EntityRef for references**, **Manager for collections**, **domain exceptions**, and **write accepts ID or entity**.
