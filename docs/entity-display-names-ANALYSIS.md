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

**API Layer (v2 DRF serializers):**
- FK fields return embedded summary objects: `"project": {"id": "xY9...", "name": "Auth System"}`
- String ID fields (claimed_by, reviewer_id, etc.) resolve to `AgentRef` or `UserRef` objects
- `?expand=` pattern for optional child collections (reviews, events, links, traces)
- Write side accepts bare IDs (unchanged): `"project": "xY9..."`
- DRF `to_representation()` handles the read/write asymmetry per field
- Responses are identical for all consumers — the SDK adapts, not the API

**Python SDK (`vtf-sdk-python`):**
- Shared by CLI, vafi controller, future vtf-kb
- Replaces `cli/vtf/client.py` and vafi's `VtfClient`
- Entity objects with `EntityRef` for FK fields, Manager pattern for collections
- Auth handling (token, session) built into client
- Published as internal package or git submodule
- Note: MCP tools do NOT use the SDK — they use ORM + v2 serializers directly (see Gap 5)

**TypeScript SDK (`vtf-sdk-ts`):**
- Used by React SPA
- Replaces ad-hoc `api/*.ts` fetch functions
- Entity types with `EntityRef` for FK fields
- React Query integration via hooks (`@vtf/sdk-react`)
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
        4d: MCP tools → v2 serializers (ORM stays, shared contract — see Gap 5)
              │
Step 5: Deprecate /v1/
        (Once all consumers confirmed on /v2/)
              │
Step 6: Remove /v1/
        (Clean break)
```

### Open Questions (for future design doc)

These need answers before implementation begins. Questions resolved during this analysis are marked.

1. **Versioning mechanism** — URL prefix (`/v2/tasks/`) vs header (`Accept: application/vnd.vtf.v2+json`) vs query param (`?version=2`). URL prefix is simplest and most visible. **Leaning:** URL prefix — most visible, easiest to debug, aligns with GitLab's approach.

2. **Shared vs separate serializers** — ~~Do v1 and v2 share a base serializer with different `to_representation()`? Or are they completely separate classes?~~ **Resolved in Gap 5:** v2 serializers are the shared contract between REST API and MCP tools. v1 serializers remain untouched. v2 serializers should be separate classes (not subclasses of v1) to avoid coupling — v1 can be deleted cleanly when deprecated.

3. ~~**MCP tools and /v2/**~~ — **Resolved in Gap 5:** MCP tools use ORM queries + v2 serializers directly. No SDK, no HTTP-to-self. The v2 serializer is the shared contract.

4. **SDK packaging** — Monorepo subfolder, separate repos, or published packages? For internal use, monorepo subfolder is simplest. For open source, published packages (`pip install vtf-sdk`, `npm install @vtf/sdk`).

5. **Migration testing** — How to verify that a consumer works correctly on /v2/ before cutting over? Shadow traffic? Feature flags? Parallel runs?

6. **Summary field selection** — Which fields belong in each summary type? Minimal (`{id, name}`) or richer (`{id, name, status, web_url}`)? The GitLab case study suggests richer summaries reduce follow-up calls, but they also increase payload size and staleness risk.

7. **v2 URL routing** — How do `/v1/` and `/v2/` coexist in Django's URL configuration? Options: separate URL modules per version, separate viewsets per version, or same viewsets with version-aware serializer selection. Needs design decision.

8. **Authorization model in SDK** — Different consumers have different roles and permissions. How does the SDK surface authorization errors and available actions? See Gap 11.

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

---

## Alternatives Considered

### Why Not GraphQL?

GraphQL is the natural "what about..." question for anyone reviewing this architecture. It directly solves the entity display name problem — a client can request exactly the nested fields it needs in a single query:

```graphql
query {
  task(id: "tsk-abc") {
    title
    status
    project { name }
    milestone { name status }
    claimedBy { name }
    requires { title status }
  }
}
```

One round-trip, no follow-up queries, no over-fetching. The client declares its data needs, the server fulfills them. This is elegant and would eliminate every issue documented in this analysis.

**However, GraphQL optimizes for a problem vtf doesn't have, while introducing costs vtf can't justify.**

#### What GraphQL Optimizes For

GraphQL excels when:
- **Many diverse clients need different shapes of the same data** — a mobile app, a desktop dashboard, a third-party integration, and an admin panel all query the same entities but need different field subsets
- **The API is public** and you cannot predict or control what clients will request
- **Bandwidth is constrained** (mobile networks) and payload minimization matters
- **The entity graph is deep and complex** — clients routinely need 4-5 levels of nested data in unpredictable combinations

#### vtf's Situation

| GraphQL Strength | vtf Reality |
|-----------------|-------------|
| Many diverse clients needing different shapes | 4-5 known consumers, all need roughly the same data |
| Public API with unpredictable client needs | Internal API where we control every consumer |
| Bandwidth-constrained mobile clients | Server-to-server (vafi, MCP) and desktop browser |
| Deep, unpredictable query patterns | Stable 4-level hierarchy (Project → Workplan → Milestone → Task) |
| Rapidly evolving frontend data needs | Entity model is mature and stable |

vtf's consumers are known, controlled, and have similar data needs. The "different clients need different shapes" problem barely exists — Task detail looks roughly the same whether the Web UI, CLI, or an MCP tool is asking.

#### Costs GraphQL Would Introduce

**1. The N+1 problem moves server-side.** In REST, the N+1 is the client's problem (it makes extra calls). In GraphQL, every nested field in a query can trigger separate database queries on the server. The standard solution — Facebook's DataLoader pattern for batching — adds significant infrastructure:

```python
# Without DataLoader: N+1 per nested field
# Query for 20 tasks with project { name } triggers 20 separate project queries

# With DataLoader: batched, but adds a layer of complexity
class ProjectLoader(DataLoader):
    async def batch_load_fn(self, project_ids):
        projects = await Project.objects.filter(id__in=project_ids)
        return [projects_by_id[pid] for pid in project_ids]
```

Django + Graphene (or Strawberry) + DataLoaders is substantially more complex than `select_related()` in a DRF serializer.

**2. HTTP caching breaks.** REST responses cache naturally — `GET /v2/tasks/tsk-abc` is a stable cache key. GraphQL uses POST requests with arbitrary query bodies. HTTP-level caching (CDN, browser cache, reverse proxy) doesn't work without additional infrastructure (persisted queries, cache key extraction).

**3. Three API surfaces instead of two.** vtf would maintain REST `/v1/` (current consumers), GraphQL (new consumers), and eventually REST `/v2/` if we still want versioned REST. Or we abandon REST entirely and go all-in on GraphQL, which is a much larger commitment.

**4. Schema duplication.** The Django models define the data shape. DRF serializers re-define it for REST. GraphQL types would re-define it again. Three places that must stay in sync. (Tools like `graphene-django` reduce this but don't eliminate it.)

**5. Query complexity risks.** An unconstrained GraphQL API lets clients write expensive queries:

```graphql
# A client could request this — joins across the entire entity graph
query {
  projects {
    workplans {
      milestones {
        tasks {
          requires { requires { requires { title } } }
          reviews { ... }
          events { ... }
        }
      }
    }
  }
}
```

This requires depth limiting, complexity analysis, and query cost budgets — infrastructure that REST doesn't need because the server controls the response shape.

**6. The SDK still needs to exist.** GraphQL gives flexible queries, but consumers still want typed entity objects with methods, lazy collections, and domain exceptions. You'd build the SDK on top of GraphQL instead of REST, but the SDK work is the same either way.

#### The Teaching Perspective

GraphQL vs REST is a valuable architectural trade-off to understand:

| Dimension | REST + SDK | GraphQL |
|-----------|-----------|---------|
| **Server controls response shape** | Yes — server decides what to include | No — client decides |
| **Client flexibility** | Limited — `?expand=` for optional fields | Full — any combination of fields |
| **Caching** | HTTP-native (URL = cache key) | Requires custom infrastructure |
| **Server complexity** | Low — serializers + `select_related()` | Higher — resolvers + DataLoaders |
| **Type safety** | SDK provides types | Schema provides types |
| **N+1 prevention** | Server-side (`select_related`) | Server-side (DataLoaders) — harder |
| **Best for** | Known consumers, stable entity model | Unknown consumers, diverse data needs |

The right choice depends on the system's characteristics, not on which technology is newer. For vtf — a system with a small number of known consumers, a stable entity hierarchy, and a reference-architecture goal that values clarity — REST `/v2/` with typed SDKs is the simpler, more teachable, and more appropriate choice.

GraphQL would be the right answer if vtf evolved into a public platform API serving hundreds of third-party integrations. That's not the current trajectory, and designing for a hypothetical future violates YAGNI (You Aren't Gonna Need It) — another principle worth demonstrating in a reference architecture.

**Importantly, the door stays open.** The `/v2/` + SDK architecture doesn't preclude adding GraphQL later. The domain layer (Django models, services, state machine, guards) is transport-agnostic. GraphQL would slot in as an additional transport alongside REST, consuming the same service layer. The SDK would gain a GraphQL backend option without consumers needing to change. Good architecture keeps options open without paying for them upfront.

### Why Not gRPC?

For completeness: gRPC with Protocol Buffers was also considered. gRPC excels at high-throughput, low-latency service-to-service communication with strict schema contracts (`.proto` files). However:

- vtf's web UI is a browser-based React SPA — gRPC requires gRPC-Web proxy for browser clients
- vtf's CLI and MCP tools benefit from human-readable JSON for debugging — Protocol Buffers are binary
- The performance characteristics gRPC optimizes for (streaming, binary encoding, HTTP/2 multiplexing) are not vtf's bottleneck
- gRPC's code generation from `.proto` files provides typed clients automatically, which is appealing, but the same can be achieved with OpenAPI code generation for REST if needed later

gRPC would be appropriate for the vafi controller ↔ vtf API path if latency became critical (high-frequency heartbeats, streaming task events). It could be introduced later as a transport optimization for that specific path without replacing the REST API for other consumers.

---

## Architectural Gap Analysis

The following gaps were identified through systematic analysis of the full lifecycle: not just reads, but writes, real-time, authentication, testing, concurrency, and edge cases. Each gap is reasoned through from first principles with SOLID and design pattern considerations.

### Gap 1: Pagination — How Do Collections Work?

**The tension:** `.list()` needs to return data from a paginated API. But the consumer shouldn't need to think about pagination for simple use cases, while retaining control for large datasets.

**Patterns considered:**

| Pattern | Example | Trade-off |
|---------|---------|-----------|
| Return all items | `tasks = vtf.tasks.list()` | Simple but dangerous — unbounded memory |
| Return a page object | `page = vtf.tasks.list(page=1, per_page=20)` | Explicit but forces pagination awareness |
| Lazy auto-paginating iterator | `for task in vtf.tasks.list(): ...` | Convenient but hides network calls |

**Decision: Two explicit methods — `.list()` and `.list_all()`**

```python
# .list() returns a single page — safe, explicit, predictable
result = vtf.tasks.list(status="doing", page=1, per_page=20)
result.items      # list[Task] — this page only
result.total      # int — total matching count
result.has_more   # bool — are there more pages?
result.page       # int — current page number

# .list_all() returns a lazy iterator that auto-paginates — convenient for "give me everything"
for task in vtf.tasks.list_all(status="doing"):
    print(task.title)
    # transparently fetches next page when current page is exhausted
```

**Design principle:** **Principle of Least Surprise.** `.list()` is safe by default (bounded). `.list_all()` is explicitly named to signal "this may fetch many pages." The consumer chooses the behavior they want. No hidden network calls in the default path.

This is the **Iterator pattern** (GoF) applied to paginated APIs. The lazy iterator encapsulates the pagination state and transparently fetches the next page when the current one is exhausted.

**TypeScript equivalent — integrates with React Query's pagination:**

```typescript
// Single page (useQuery)
const { data } = useTasksPage({ status: 'doing', page: 1, perPage: 20 });
data.items;   // Task[]
data.total;   // number

// Infinite scroll (useInfiniteQuery)
const { data, fetchNextPage, hasNextPage } = useInfiniteTasks({ status: 'doing' });
```

---

### Gap 2: Sync vs Async — The Python SDK Serves Two Worlds

**The tension:** The Python SDK serves:
- CLI (sync — Click is synchronous)
- MCP tools (sync — Django ORM, though in an async event loop)
- vafi controller (async — `httpx.AsyncClient`, asyncio event loop)

A single client API cannot be both sync and async without compromise.

**Patterns considered:**

| Pattern | Example | Trade-off |
|---------|---------|-----------|
| Async-first, sync wrapper via `asyncio.run()` | `vtf.tasks.get(id)` internally calls `asyncio.run(self._aget(id))` | Breaks if called from an existing event loop (vafi) |
| Sync-first, async wrapper via `run_in_executor` | `await vtf.tasks.get(id)` internally runs sync HTTP in threadpool | Wastes threads, doesn't benefit from async I/O |
| Two separate clients | `VtfClient` (sync) and `AsyncVtfClient` (async) | Code duplication risk |
| Single client parametric over transport | Shared entity logic, swappable HTTP backend | Complex but clean |

**Decision: Two clients, shared entity layer — following httpx's own pattern**

```python
# Sync (CLI, tests)
from vtf_sdk import VtfClient
vtf = VtfClient(url="...", token="...")
task = vtf.tasks.get(task_id)

# Async (vafi controller)
from vtf_sdk import AsyncVtfClient
vtf = AsyncVtfClient(url="...", token="...")
task = await vtf.tasks.get(task_id)
```

Both return identical `Task` entity objects. The difference is only in the transport layer. Internally:

```python
class BaseTaskManager:
    """Shared entity construction logic — no I/O here."""

    def _build_task(self, data: dict) -> Task:
        return Task(
            id=data["id"],
            title=data["title"],
            project=ProjectRef(id=data["project"]["id"], name=data["project"]["name"]),
            ...
        )

class TaskManager(BaseTaskManager):
    """Sync transport."""
    def get(self, id: str) -> Task:
        data = self._client.get(f"/v2/tasks/{id}/")  # httpx.Client
        return self._build_task(data)

class AsyncTaskManager(BaseTaskManager):
    """Async transport."""
    async def get(self, id: str) -> Task:
        data = await self._client.get(f"/v2/tasks/{id}/")  # httpx.AsyncClient
        return self._build_task(data)
```

**Design principle:** **Strategy pattern** — the HTTP transport strategy (sync vs async) is swappable while the entity model remains constant. **Interface Segregation** — sync consumers import `VtfClient`, async consumers import `AsyncVtfClient`. Neither is burdened with the other's concerns.

**Risk mitigation:** The entity construction logic in `BaseTaskManager._build_task()` is the shared kernel. Unit tests verify that both `TaskManager` and `AsyncTaskManager` produce identical entity objects from the same input dict. If one drifts, tests catch it.

---

### Gap 3: Real-Time (SSE) in the TypeScript SDK

**The tension:** The web UI receives Server-Sent Events for real-time updates. Currently, every event triggers `queryClient.invalidateQueries()` — a full refetch. The SDK should do better, but coupling the SDK to React Query's cache is a framework dependency.

**Design: Layered — core event emitter + framework adapter**

```
@vtf/sdk           — core: entities, managers, typed event emitter (framework-agnostic)
@vtf/sdk-react     — React integration: hooks, React Query cache sync, SSE → cache bridge
```

**Core SDK emits typed domain events:**

```typescript
// @vtf/sdk — framework-agnostic
const events = vtf.events.subscribe({ projectId: project.id });

events.on('task.statusChanged', (event: TaskStatusChangedEvent) => {
  event.taskId;     // string
  event.taskTitle;  // string — from enriched SSE payload
  event.fromStatus; // TaskStatus
  event.toStatus;   // TaskStatus
});

events.close();
```

**React adapter bridges events to cache:**

```typescript
// @vtf/sdk-react — React-specific
import { useVtfEvents } from '@vtf/sdk-react';

function WorkplanBoard({ workplanId }) {
  // This hook:
  // 1. Subscribes to SSE events filtered by workplan
  // 2. On task.statusChanged: updates the cached Task entity in React Query
  // 3. On task.created: adds to the cached task list
  // 4. On cleanup: closes the EventSource connection
  useVtfEvents({ workplanId });

  // These hooks now get real-time updates via cache, no manual event handling
  const { data: tasks } = useTasks({ workplanId });
  // ...
}
```

**Design principle:** **Adapter pattern** — `@vtf/sdk-react` adapts the core SDK's event emitter to React Query's cache API. **Dependency Inversion** — the core SDK doesn't depend on React or React Query. The framework-specific layer depends on the core, not vice versa.

**This also means:** If someone builds a Vue or Svelte frontend for vtf, they write a `@vtf/sdk-vue` adapter without touching the core SDK.

---

### Gap 4: The Link Model — Polymorphic References

**The tension:** A Link connects any entity type to any other. The source can be a task, milestone, or workplan. The target can be any of those OR an external reference (Jira ticket, commit SHA, KB area). The summary shape depends on the type.

**Current v1 shape:**
```json
{
  "source_type": "task",
  "source_id": "tsk-abc",
  "source_title": "Add auth",
  "target_type": "jira",
  "target_id": "PROJ-1234",
  "target_title": null,
  "link_type": "relates_to"
}
```

**v2 target shape — discriminated union:**

```json
{
  "source": {
    "type": "task",
    "id": "tsk-abc",
    "title": "Add auth",
    "status": "doing"
  },
  "target": {
    "type": "jira",
    "id": "PROJ-1234",
    "label": "PROJ-1234"
  },
  "link_type": "relates_to"
}
```

For internal entities (task, milestone, workplan), the embedded summary uses that entity's standard `Ref` type (TaskRef, MilestoneRef, WorkplanRef). For external references, a minimal `ExternalRef` with `{type, id, label}`.

**TypeScript models this naturally as a discriminated union:**

```typescript
type InternalRef =
  | { type: 'task'; id: string; title: string; status: TaskStatus }
  | { type: 'milestone'; id: string; name: string; status: MilestoneStatus }
  | { type: 'workplan'; id: string; name: string };

type ExternalRef = {
  type: 'commit' | 'jira' | 'doc' | 'file' | 'area';
  id: string;
  label: string;  // human-readable display text
};

type LinkRef = InternalRef | ExternalRef;

interface Link {
  id: string;
  source: InternalRef;         // source is always an internal entity
  target: LinkRef;             // target can be internal or external
  linkType: LinkType;
}
```

**Python uses a base class with typed subclasses:**

```python
class InternalRef:
    type: str   # "task" | "milestone" | "workplan"
    id: str
    name: str   # title for tasks, name for others
    status: str | None

class ExternalRef:
    type: str   # "commit" | "jira" | "doc" | "file" | "area"
    id: str
    label: str

LinkRef = InternalRef | ExternalRef  # Python 3.10+ union

class Link:
    id: str
    source: InternalRef
    target: LinkRef
    link_type: str
```

**Design principle:** **Liskov Substitution** — any `LinkRef` can be displayed by calling `.label` (for external) or `.name` (for internal). The consumer doesn't need to know the concrete type to show a human-readable label. We can achieve this with a shared property:

```python
class InternalRef:
    @property
    def display_name(self) -> str:
        return self.name

class ExternalRef:
    @property
    def display_name(self) -> str:
        return self.label
```

Now any `LinkRef` has `.display_name` — the consumer can always show something meaningful regardless of type.

**Performance note:** The current N+1 in `LinkSerializer.get_target_title()` is eliminated in v2. The serializer batch-loads all referenced entities in `to_representation()` using a single query per entity type, then inlines the summaries. This is the same approach Django's `prefetch_related()` uses.

---

### Gap 5: MCP Tools — SDK, ORM, or Shared Serializers?

**The tension:** MCP tools run inside the Django process. Three options:

| Option | How MCP tools get data | How MCP tools format responses |
|--------|----------------------|-------------------------------|
| **A: Use Python SDK** | HTTP calls to self | SDK entity objects → JSON |
| **B: Use ORM directly** | Django ORM queries | Hand-built dicts (current) |
| **C: Use ORM + v2 serializers** | Django ORM queries | v2 serializers → JSON |

**Analysis of each option:**

**Option A (SDK)** violates common sense. The MCP server runs inside the Django process. Making HTTP calls to yourself introduces network latency, requires auth tokens for your own process, and creates a circular dependency. This is a code smell — using a remote interface for a local call.

**Option B (ORM directly)** is what exists today. The problem: each MCP tool formats its own response dict, and these shapes drift from the REST API's v2 contract. An LLM agent using MCP tools sees different field names and structures than a consumer using the REST API. This violates the **Uniform Interface** principle — the same entity should look the same regardless of access method.

**Option C (ORM + v2 serializers)** is the right answer. MCP tools query the ORM (efficient, in-process, no HTTP overhead) but delegate response formatting to the v2 serializers (shared contract, consistent shapes):

```python
@mcp.tool()
def vtf_task_detail(task_id: str) -> str:
    task = (Task.objects
        .select_related('project', 'workplan', 'milestone')
        .get(id=task_id))
    data = TaskSerializerV2(task).data
    return json.dumps(success_response(data=data))
```

**Design principle:** **Shared Kernel** (Domain-Driven Design) — the v2 serializer is the shared contract between the REST API and MCP tools. Both use the same serializer, so responses are guaranteed to have the same shape. The serializer is the single source of truth for "what does a Task look like in v2."

**This also means:** When we add a field to the v2 Task response, it automatically appears in both the REST API and MCP tools. No separate update needed. DRY by construction.

**What about the SDK entity types?** The Python SDK's `Task` class is built from the v2 serializer's output shape. The MCP tools return that same shape as JSON. An LLM agent that uses MCP tools and a Python SDK consumer see the same data. The SDK is not needed inside the MCP tools — the serializer provides the contract.

---

### Gap 6: Bulk Operations

**The tension:** vtf has bulk import (`POST /v1/bulk/import`). The vafi supervisor may dispatch multiple claims. Does the SDK need a generic batch framework?

**Analysis:** vtf's bulk needs are specific and limited:
- Bulk import of tasks from YAML specs
- Potentially batch claim (supervisor dispatching to multiple agents)
- Potentially batch status updates (cancel all tasks in a milestone)

These are **domain-specific batch operations**, not generic "execute N arbitrary mutations in one call."

**Decision: Domain-specific bulk methods, not a generic batch framework**

```python
# Specific bulk operations as SDK methods
results = vtf.bulk.import_tasks(
    workplan_id=wp.id,
    tasks=[TaskSpec(title="...", ...), ...]
)
# returns: list[Task] (created entities)

# Individual operations for everything else — looping is fine at vtf's scale
for task_id in task_ids:
    vtf.tasks.claim(task_id, agent_id=agent.id)
```

**Design principle:** **YAGNI** — don't build a generic batch framework for a system that has 2-3 specific bulk operations. Add bulk endpoints when a concrete need arises. A generic `vtf.batch([op1, op2, op3])` API adds complexity without solving a real problem at vtf's scale.

**The import endpoint already exists.** Give it an SDK method. Don't over-abstract.

---

### Gap 7: SDK Testing Contract

**The tension:** If testing with the SDK is harder than testing with raw JSON dicts, consumers won't adopt it. The SDK must provide first-class testing support.

**Three levels of testing support, each serving a different need:**

**Level 1: Protocol (interface) for dependency injection**

```python
# The SDK defines a Protocol (abstract interface)
from vtf_sdk.protocols import VtfClientProtocol, TaskManagerProtocol

class VtfClientProtocol(Protocol):
    @property
    def tasks(self) -> TaskManagerProtocol: ...
    @property
    def projects(self) -> ProjectManagerProtocol: ...
    @property
    def workplans(self) -> WorkplanManagerProtocol: ...
```

Consumer code depends on the Protocol, not the concrete `VtfClient`. Any test double that satisfies the Protocol works:

```python
# Consumer code
def process_tasks(vtf: VtfClientProtocol):
    for task in vtf.tasks.list_all(status="doing"):
        ...

# Test
mock_vtf = MockVtfClient()
process_tasks(mock_vtf)  # works — MockVtfClient satisfies VtfClientProtocol
```

**Design principle:** **Dependency Inversion** — consumer depends on abstraction (Protocol), not implementation (VtfClient).

**Level 2: MockVtfClient — in-memory implementation**

```python
from vtf_sdk.testing import MockVtfClient

vtf = MockVtfClient()
vtf.seed_project(id="p1", name="Auth System")
vtf.seed_task(id="t1", title="Add auth", project_id="p1")

# Now vtf.projects.get("p1") returns a real Project entity
# vtf.tasks.list(project="p1") returns the seeded task
# vtf.tasks.claim("t1", agent_id="a1") updates the in-memory state
```

The mock implements the full Protocol with in-memory storage. It simulates the API behavior without HTTP. State mutations work — claiming a task changes its status in the mock.

**Level 3: Entity factories for unit tests**

```python
from vtf_sdk.testing import build_task, build_project

# Create entity objects directly, no client needed
task = build_task(
    title="Add auth",
    project=build_project(name="Auth System"),
    status="doing",
)

# Use in tests that don't need API behavior, just entity objects
assert task.project.name == "Auth System"
```

**TypeScript equivalent:**

```typescript
import { createMockClient, buildTask, buildProject } from '@vtf/sdk/testing';

// Full mock client
const vtf = createMockClient({
  projects: [buildProject({ name: 'Auth System' })],
  tasks: [buildTask({ title: 'Add auth' })],
});

// Or just entity factories
const task = buildTask({ title: 'Add auth', project: buildProject({ name: 'Auth System' }) });
expect(task.project.name).toBe('Auth System');
```

**Design principle:** **Test Pyramid** — factories for unit tests (fast, no I/O), MockVtfClient for integration tests (in-memory behavior), real VtfClient for E2E tests (actual API).

---

### Gap 8: Write-Side Design

**The tension:** We focused on reads. But the SDK also wraps mutations — create, update, state transitions. These have their own design concerns.

**State machine transitions as explicit methods:**

```python
# Each transition is a named method — not a generic "update status"
task = vtf.tasks.submit(task_id)      # draft → todo
task = vtf.tasks.claim(task_id, agent_id=agent.id)  # todo → doing
task = vtf.tasks.complete(task_id)    # doing → pending_completion_review
task = vtf.tasks.fail(task_id)        # doing → needs_attention
task = vtf.tasks.recover(task_id, target="todo")  # needs_attention → todo
task = vtf.tasks.block(task_id, reason="Waiting on dependency")
task = vtf.tasks.unblock(task_id)
```

**Why named methods, not `vtf.tasks.update(id, status="doing")`:**
- The state machine has guards and side effects. `claim` requires an `agent_id`. `recover` requires a `target`. A generic update doesn't express these constraints.
- Named methods make valid transitions discoverable via IDE autocomplete.
- Invalid transitions (e.g., `complete` on a `draft` task) raise `InvalidTransition`, not a generic 400 error.

**Every mutation returns the updated entity:**

```python
task = vtf.tasks.claim(task_id, agent_id=agent.id)
# task is a full Task entity with:
#   task.status == "doing"
#   task.claimed_by.name == "executor-1"
#   task.project.name == "Auth System"
# The consumer always has current state after a mutation.
```

**Design principle:** **Command pattern** — each state transition is a distinct command with its own parameters and preconditions. The SDK surface area reflects the domain's valid operations, not the HTTP verbs.

**Domain-specific exceptions:**

```python
from vtf_sdk.exceptions import (
    InvalidTransition,    # wrong status for this action
    GuardViolation,       # precondition not met (e.g., no workplan)
    ClaimConflict,        # task already claimed by another agent
    TaskNotFound,         # 404
    ValidationError,      # invalid field values
    PermissionDenied,     # not authorized
)

try:
    vtf.tasks.claim(task_id, agent_id=agent.id)
except ClaimConflict as e:
    print(f"Already claimed by {e.held_by}")
except GuardViolation as e:
    print(f"Cannot claim: {e.guard_name} — {e.message}")
except InvalidTransition as e:
    print(f"Task is {e.current_status}, cannot transition via claim")
```

**Design principle:** **Replace error codes with exceptions** (Refactoring, Fowler). The consumer catches domain concepts (`ClaimConflict`), not transport artifacts (`HTTPError(409)`). Each exception carries contextual data (who holds the claim, which guard failed).

**No client-side validation:** The SDK does not validate locally before sending. Server-side validation is authoritative. Client-side validation drifts from the server and creates false confidence. The SDK sends the request and maps the server's error response to typed exceptions.

**TypeScript — optimistic updates in React:**

```typescript
// @vtf/sdk-react provides mutation hooks
const { mutate: claimTask } = useClaimTask({
  // Optimistic update: immediately update UI
  onMutate: (taskId) => {
    queryClient.setQueryData(['task', taskId], old => ({
      ...old,
      status: 'doing',
      claimedBy: currentAgent,
    }));
  },
  // Revert on failure
  onError: (err, taskId) => {
    queryClient.invalidateQueries({ queryKey: ['task', taskId] });
  },
});
```

The React adapter provides pre-built mutation hooks with optimistic update logic. The consumer gets real-time UI updates with automatic rollback on failure.

---

### Gap 9: Authentication Lifecycle

**The tension:** Different consumers authenticate differently. The SDK must handle this transparently.

**Auth strategies:**

| Consumer | Auth Method | SDK Configuration |
|----------|-----------|-------------------|
| CLI | Token (from `vtf config`) | `VtfClient(token="...")` |
| vafi controller | Service account token (env var) | `AsyncVtfClient(token=os.environ["VTF_API_TOKEN"])` |
| React SPA | Session cookie (browser) | `VtfClient({ credentials: 'include' })` |
| MCP tools | N/A (in-process, uses Django ORM) | No SDK auth needed |

**Decision: Auth is a constructor concern, not a per-request concern**

```python
# Token auth (most consumers)
vtf = VtfClient(url="...", token="my-token")

# The SDK sends Authorization: Token my-token on every request
# The consumer never thinks about auth after construction
```

```typescript
// Session auth (browser)
const vtf = new VtfClient({ baseUrl: '/api', credentials: 'include' });

// Cookie sent automatically by browser
```

**Future-proofing for OAuth:** vtf currently uses static tokens (DRF TokenAuthentication). If OAuth is added later, the SDK supports a pluggable auth strategy:

```python
# Static token (current)
vtf = VtfClient(url="...", auth=TokenAuth("my-token"))

# OAuth with refresh (future)
vtf = VtfClient(url="...", auth=OAuthAuth(
    client_id="...",
    client_secret="...",
    token_url="...",
))

# Custom auth (extensible)
vtf = VtfClient(url="...", auth=CustomAuth(lambda request: add_my_headers(request)))
```

**Design principle:** **Strategy pattern** — the auth mechanism is a pluggable strategy injected at construction time. **Open/Closed** — the SDK is open for new auth methods without modifying the client code.

**Token is the sensible default:** For convenience, `VtfClient(url="...", token="...")` is syntactic sugar for `VtfClient(url="...", auth=TokenAuth("..."))`. The simple case stays simple.

---

### Gap 10: OpenAPI and Schema Generation

**The tension:** Should the SDK be auto-generated from an OpenAPI spec, or hand-written?

**Analysis:**

| Approach | Sync Guarantee | Ergonomics | Effort |
|----------|---------------|------------|--------|
| **Generated from OpenAPI** | Automatic — spec changes regenerate SDK | Poor — generated code is flat, no lazy loading, no domain methods | Low initial, high customization |
| **Hand-written SDK** | Manual — must update SDK when API changes | Excellent — full control over entity objects, managers, patterns | Higher initial, lower maintenance |
| **Hand-written SDK + OpenAPI for validation** | CI-enforced — tests verify SDK types match spec | Excellent | Moderate |

**Decision: Hand-written SDK, validated against OpenAPI spec in CI**

1. **DRF generates the OpenAPI spec** (via `drf-spectacular`) — this is documentation and a machine-readable contract.
2. **The SDK is hand-written** — full control over ergonomics (entity objects, lazy collections, managers, domain exceptions).
3. **CI tests validate alignment** — a test suite fetches the OpenAPI spec and verifies that every SDK entity type matches the corresponding schema. If the API adds a field and the SDK doesn't, CI fails.

```python
# In SDK test suite
def test_task_entity_matches_openapi_schema():
    spec = load_openapi_spec("https://vtf.example.com/v2/schema/")
    task_schema = spec["components"]["schemas"]["Task"]
    task_fields = set(task_schema["properties"].keys())
    sdk_fields = set(Task.__dataclass_fields__.keys())
    assert task_fields == sdk_fields, f"Drift detected: {task_fields ^ sdk_fields}"
```

**Design principle:** This follows Stripe's approach — they have an OpenAPI spec but hand-craft their SDKs for ergonomics. The spec is the source of truth for the API contract; the SDK is the source of truth for the developer experience. CI ensures they don't drift.

---

### Gap Summary

| Gap | Decision | Design Pattern | Principle |
|-----|----------|---------------|-----------|
| **Pagination** | `.list()` returns page, `.list_all()` returns lazy iterator | Iterator | Least Surprise |
| **Sync/Async** | Two clients (`VtfClient`, `AsyncVtfClient`), shared entity layer | Strategy | Interface Segregation |
| **Real-time (SSE)** | Core event emitter + `@vtf/sdk-react` adapter for cache sync | Adapter, Observer | Dependency Inversion |
| **Link model** | Discriminated union with `InternalRef` / `ExternalRef`, shared `.display_name` | Polymorphism | Liskov Substitution |
| **MCP tools** | ORM queries + v2 serializers (no SDK, no HTTP-to-self) | Shared Kernel (DDD) | DRY, Uniform Interface |
| **Bulk operations** | Domain-specific bulk methods, not generic batch framework | — | YAGNI |
| **Testing** | Protocol + MockVtfClient + entity factories (three levels) | Dependency Injection | Dependency Inversion |
| **Write side** | Named transition methods, return updated entity, domain exceptions | Command | Replace error codes with exceptions |
| **Authentication** | Pluggable auth strategy, token as default | Strategy | Open/Closed |
| **Schema** | Hand-written SDK, OpenAPI spec for CI validation | — | Stripe pattern |

---

### Gap 11: Authorization — Not All Clients Are Equal

**The tension:** We covered authentication (Gap 9 — proving identity), but not authorization (what actions each identity is allowed to perform). vtf has a role-based permission model, and different consumers operate at different privilege levels.

**Current authorization landscape:**

| Consumer | Identity Type | Role | What They Can Do |
|----------|-------------|------|-----------------|
| **Web UI (human, project owner)** | Human user | owner | Full CRUD on project, workplans, tasks, members |
| **Web UI (human, project member)** | Human user | member | CRUD on tasks/workplans, cannot manage members |
| **Web UI (human, project viewer)** | Human user | viewer | Read-only access to project scope |
| **CLI (human, staff)** | Human user | staff | Bypass project membership, access all projects |
| **vafi controller** | Service account | agent | Claim, complete, fail tasks; post notes and reviews |
| **MCP tools (architect agent)** | Service account or human | varies | Create workplans, plan tasks, manage milestones |
| **MCP tools (executor agent)** | Service account | agent | Claim and execute tasks in assigned project |
| **Cross-service (vtf-kb)** | Service account | service | Read-only access to task metadata for knowledge indexing |

**The key architectural insight:** Authorization is enforced on the **server** (Django's `HasProjectMembership` permission, `IsStaff`, role checks). The SDK should **not** duplicate authorization logic. But the SDK should:

1. **Surface authorization errors as typed exceptions** — not HTTP 403
2. **Expose the user's permissions** so the UI can show/hide actions
3. **Carry the authorization context** (role, project membership) from auth/validate response

**Authorization in SDK responses:**

The v2 API already returns `available_actions` in MCP tool responses. This should be formalized across all v2 endpoints:

```json
// GET /v2/tasks/tsk-abc
{
  "id": "tsk-abc",
  "title": "Add auth endpoint",
  "status": "todo",
  "project": {"id": "xY9...", "name": "Auth System"},
  "_permissions": {
    "can_claim": true,
    "can_edit": true,
    "can_delete": false,
    "can_submit": false,
    "available_transitions": ["claim", "block", "defer", "cancel"]
  }
}
```

The `_permissions` object (prefixed with `_` to signal it's metadata, not entity data) tells the consumer what the current user can do with this entity. The SDK exposes this:

```python
task = vtf.tasks.get(task_id)
task.permissions.can_claim          # True
task.permissions.available_transitions  # ["claim", "block", "defer", "cancel"]

if task.permissions.can_claim:
    vtf.tasks.claim(task.id, agent_id=agent.id)
```

```typescript
const task = await vtf.tasks.get(id);

// UI conditionally renders buttons based on permissions
{task.permissions.canClaim && <ClaimButton taskId={task.id} />}
{task.permissions.canEdit && <EditButton taskId={task.id} />}
```

**Why server-computed permissions, not client-side role checks:**

The alternative — `if (user.role === 'owner') showDeleteButton()` — is fragile. Permission logic lives in Django's permission classes and the state machine guards. Duplicating it in the SDK means two places that can disagree. The server is authoritative; the SDK reflects what the server says.

**Authorization errors as domain exceptions:**

```python
from vtf_sdk.exceptions import PermissionDenied, ProjectAccessDenied

try:
    vtf.tasks.delete(task_id)
except ProjectAccessDenied as e:
    print(f"No access to project {e.project_name} (your role: {e.role})")
except PermissionDenied as e:
    print(f"Action not allowed: {e.action} — {e.reason}")
```

**Service account scopes:**

vtf's `create_service_account` management command creates agent-type users. In the SDK, service accounts authenticate like any other token user, but their permissions are limited by their role and project membership. The SDK doesn't need special service account handling — the server enforces the boundaries.

**Design principle:** **Single Source of Truth** for authorization — the server. The SDK is a faithful mirror, not an independent authority. **Tell, Don't Ask** — the server tells the consumer what's allowed via `_permissions`, rather than the consumer asking "am I allowed?" and computing the answer locally.

---

### Gap 12: Entity Immutability

**The tension:** If SDK entity objects are mutable, consumers can accidentally modify cached state, creating subtle bugs — especially with React Query's cache.

**Decision: Entities are immutable. Mutations return new instances.**

```python
# Python SDK — entities are frozen dataclasses
from dataclasses import dataclass

@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: str
    project: ProjectRef
    workplan: WorkplanRef | None
    milestone: MilestoneRef | None
    claimed_by: AgentRef | None

# This raises FrozenInstanceError:
task.status = "doing"  # TypeError!

# Mutations return a new Task instance:
claimed_task = vtf.tasks.claim(task.id, agent_id=agent.id)
# claimed_task is a NEW Task object with status="doing"
# task is unchanged — still status="todo"
```

```typescript
// TypeScript SDK — entities are readonly interfaces
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

**Why this matters for React Query:** React Query compares object references to detect changes. If the SDK mutated a cached Task in-place, React would not re-render — the reference is the same. Immutable entities guarantee that a new entity means a new object reference, which triggers re-render.

**Design principle:** **Value Object** (DDD) — entity instances represent a snapshot in time. They are values, not live references to server state. If the server state changes, you get a new snapshot (via a fresh fetch or mutation response).

---

### Gap 13: Nullable References in the v2 Contract

**The tension:** Task's `workplan` and `milestone` are nullable ForeignKeys. The v2 response must clearly define what `null` looks like — is it `null`, absent, or an empty object?

**Decision: Null references are JSON `null`, never absent, never empty objects.**

```json
// Task with all references populated
{
  "project": {"id": "xY9...", "name": "Auth System"},
  "workplan": {"id": "aBc...", "name": "Platform Hardening"},
  "milestone": {"id": "zZz...", "name": "Phase 1 Core"},
  "claimed_by": {"id": "agt...", "name": "executor-1"}
}

// Task with no workplan, no milestone, unclaimed
{
  "project": {"id": "xY9...", "name": "Auth System"},
  "workplan": null,
  "milestone": null,
  "claimed_by": null
}
```

**Rules:**
- `null` means "not set" — the field is present but has no value
- Fields are **never omitted** — every response includes every field, even if null
- Empty objects `{}` are never used — that would be ambiguous (is it a ref with no data, or no ref?)

**SDK handling:**

```python
# Python
task.workplan          # WorkplanRef or None
task.workplan.name     # raises AttributeError if None — consumer must check
task.milestone?.name   # N/A in Python, use: task.milestone.name if task.milestone else None
```

```typescript
// TypeScript — optional chaining
task.workplan?.name    // string | undefined
task.milestone?.name   // string | undefined
```

**Design principle:** **Explicit over implicit.** `null` is a clear signal. Missing fields are ambiguous — was it omitted intentionally or is the API broken? Always-present fields with `null` values make the contract unambiguous.

---

### Gap 14: Resolving String ID Fields (`claimed_by`, `assigned_to`, `reviewer_id`)

**The tension:** These fields are `CharField` on the Django model — not ForeignKeys. You cannot `select_related()` on them. Resolving `claimed_by` to an `AgentRef` requires a separate query to the Agent table. This has a query cost that FK resolution (via `select_related`) does not.

**Current state:** `claimed_by`, `assigned_to`, `created_by`, `reviewer_id`, `actor_id`, `triggered_by` are all plain string fields storing agent or user IDs. There is no FK constraint to Agent or User.

**Why they're not FKs:** These fields can reference either an Agent (nanoid ID) or a Django User (integer ID). A single FK can't point at two different tables. Additionally, the value may reference an entity that no longer exists (deleted agent, deactivated user).

**Resolution approach for v2 serializers:**

```python
class TaskSerializerV2(serializers.ModelSerializer):
    claimed_by = serializers.SerializerMethodField()

    def get_claimed_by(self, obj):
        if not obj.claimed_by:
            return None
        # Try Agent first (most common for claimed_by)
        from agents.models import Agent
        try:
            agent = Agent.objects.values('id', 'name').get(id=obj.claimed_by)
            return {"id": agent["id"], "name": agent["name"]}
        except Agent.DoesNotExist:
            pass
        # Fall back to User
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.values('pk', 'username').get(pk=obj.claimed_by)
            return {"id": str(user["pk"]), "name": user["username"]}
        except (User.DoesNotExist, ValueError):
            # ID exists but entity is gone — return degraded ref
            return {"id": obj.claimed_by, "name": obj.claimed_by}
    ```

**Performance concern:** This is a per-row query — the same N+1 problem as the current `claimed_by_pod_name`. For list endpoints returning 20+ tasks, this means 20+ extra queries.

**Mitigation: Batch resolution in list serializers.**

```python
class TaskListSerializerV2(serializers.ListSerializer):
    def to_representation(self, data):
        # Collect all claimed_by IDs across all tasks in the page
        agent_ids = {t.claimed_by for t in data if t.claimed_by}

        # Single batch query
        from agents.models import Agent
        agents = {a.id: a.name for a in Agent.objects.filter(id__in=agent_ids).only('id', 'name')}

        # Pass lookup dict to child serializer via context
        self.context['_agent_cache'] = agents
        return super().to_representation(data)
```

The child serializer uses the cached lookup instead of per-row queries. This turns N queries into 1. Same pattern can batch-resolve `reviewer_id`, `actor_id`, `triggered_by`.

**Design principle:** **Batch loading** — the same principle behind Facebook's DataLoader and Django's `prefetch_related()`. Collect IDs, batch-query, distribute results.

**Degraded references:** If the referenced agent/user no longer exists, the v2 response returns a degraded ref: `{"id": "the-original-id", "name": "the-original-id"}`. The SDK creates an `EntityRef` where `name == id` — the consumer sees the ID as a fallback, not an error. This is better than returning `null` (which would hide that a reference exists) or raising an error (which would break the response for one stale reference).

---

### Gap 15: v2 URL Routing in Django

**The tension:** `/v1/` and `/v2/` must coexist in the same Django application. How do we route them without duplicating viewsets?

**Options:**

| Approach | How it works | Trade-off |
|----------|-------------|-----------|
| **Separate URL modules** | `v1/urls.py`, `v2/urls.py`, each with own router | Clean separation but duplicates URL patterns |
| **Separate viewsets per version** | `TaskViewSetV1`, `TaskViewSetV2` | Maximum control but significant code duplication |
| **Same viewsets, version-aware serializer** | One `TaskViewSet` selects serializer based on URL prefix | DRY but mixes concerns in the viewset |
| **Middleware-based version detection** | Middleware sets `request.api_version`, viewset reads it | Clean viewset code but implicit version passing |

**Recommended approach: Same viewsets, versioned serializer selection via mixin**

```python
# src/core/versioning.py
class VersionedSerializerMixin:
    """Viewset mixin that selects serializer class based on API version."""
    serializer_class_v1 = None  # set in viewset
    serializer_class_v2 = None  # set in viewset

    def get_serializer_class(self):
        if self.request.version == 'v2':
            return self.serializer_class_v2
        return self.serializer_class_v1

# src/tasks/views.py
class TaskViewSet(VersionedSerializerMixin, ModelViewSet):
    serializer_class_v1 = TaskSerializer       # existing
    serializer_class_v2 = TaskSerializerV2     # new
    queryset = Task.objects.all()

# src/vtaskforge/urls.py
from rest_framework.versioning import URLPathVersioning

urlpatterns = [
    path('v1/', include('tasks.urls')),
    path('v2/', include('tasks.urls')),  # same URL module, different serializers
]
```

DRF's built-in `URLPathVersioning` sets `request.version` based on the URL prefix. The viewset logic, queryset, permissions, and validation stay the same — only the serializer changes. This is the minimum-duplication approach.

**v2 viewsets add `select_related()` to querysets** for efficient summary resolution:

```python
class TaskViewSet(VersionedSerializerMixin, ModelViewSet):
    def get_queryset(self):
        qs = Task.objects.all()
        if self.request.version == 'v2':
            qs = qs.select_related('project', 'workplan', 'milestone')
        return qs
```

---

### Gap 16: SDK Versioning and Backward Compatibility

**The tension:** When the v2 API adds a new field (e.g., `Task.priority`), the SDK must add it too. Does this break existing consumers that don't expect the new field?

**Decision: SDK follows semantic versioning. New fields are minor versions, not breaking.**

- **Adding a field to an entity** = minor version bump (0.2.0 → 0.3.0). Existing consumers ignore the new field — frozen dataclasses allow extra fields in the response dict.
- **Removing or renaming a field** = major version bump (0.3.0 → 1.0.0). This is a breaking change.
- **Adding a new manager method** = minor version bump. Existing consumers don't call it.
- **Changing a method signature** = major version bump.

**The SDK's entity builder is lenient on input, strict on output:**

```python
@classmethod
def from_dict(cls, data: dict) -> 'Task':
    # Ignores unknown fields in the dict (forward-compatible)
    # Raises if required fields are missing (contract enforcement)
    return cls(
        id=data["id"],
        title=data["title"],
        project=ProjectRef.from_dict(data["project"]),
        # ... only extracts known fields
    )
```

This means: when the API returns a new field, the SDK ignores it until the SDK is updated. No crash, no break. When the SDK adds the field in the next release, consumers who upgrade get it; consumers who don't upgrade continue working.

---

### Gap 17: `?expand=` Interaction with SDK Lazy Loading

**The tension:** The v2 API supports `?expand=reviews,events,links` for optional child collections. The SDK has lazy loading via managers. How do these interact?

**Decision: `expand` pre-populates the manager, bypassing the lazy fetch.**

```python
# Without expand — lazy loading
task = vtf.tasks.get(task_id)
task.reviews  # triggers GET /v2/tasks/{id}/reviews/ on first access

# With expand — pre-populated from the initial response
task = vtf.tasks.get(task_id, expand=["reviews", "events"])
task.reviews  # already loaded — no extra call
task.events   # already loaded — no extra call
task.links    # NOT expanded — triggers lazy fetch on access
```

The SDK detects whether the API response included expanded collections and pre-populates accordingly. If the collection was not expanded, the manager falls back to lazy fetching.

```python
class Task:
    def __init__(self, ..., _reviews: list[Review] | None = None):
        self._reviews_cache = _reviews  # pre-populated if expanded

    @cached_property
    def reviews(self) -> list[Review]:
        if self._reviews_cache is not None:
            return self._reviews_cache
        return self._client.list_reviews(task_id=self.id)
```

**TypeScript equivalent:**

```typescript
// Without expand
const task = await vtf.tasks.get(id);
const reviews = await task.reviews.list();  // separate call

// With expand
const task = await vtf.tasks.get(id, { expand: ['reviews'] });
// task._reviews is pre-populated
const reviews = await task.reviews.list();  // returns cached data, no call
```

**Design principle:** **Optimization hint, not behavioral change.** `expand` is a performance optimization — it pre-loads data that would otherwise be lazy-loaded. The consumer code is the same either way (`task.reviews`). The only difference is when the HTTP call happens.

---

### Gap 18: Staleness of Embedded Names

**The tension:** If a project is renamed from "Auth System" to "Identity Platform", tasks fetched before the rename still carry `project.name == "Auth System"` in their `ProjectRef`. The embedded name is a snapshot, not a live reference.

**Analysis:** This is inherent to any embedded summary pattern. GitLab has the same characteristic. The question is: does it matter?

**At vtf's scale: no.** Reasons:
- Projects, workplans, and milestones are rarely renamed
- UI pages refetch data frequently (React Query stale time, SSE invalidation)
- The SDK returns immutable snapshots (Gap 12) — there's no illusion of live data
- The embedded name is a display hint, not an authoritative record — if the consumer needs the current name, they fetch the full entity

**Mitigation for edge cases:**
- React Query's `staleTime` / `refetchOnWindowFocus` naturally refreshes data
- SSE events trigger cache invalidation for affected entities
- The SDK does NOT cache entity objects across calls — each `.get()` returns a fresh snapshot

**Documentation note for SDK consumers:** The SDK's entity objects represent a point-in-time snapshot. Display names in `EntityRef` objects reflect the name at the time of the API call. If an entity is renamed, previously fetched references will show the old name until re-fetched.

**Design principle:** **Eventual consistency is acceptable for display names.** The SDK is not a distributed database — it's a view layer. Stale display names are a cosmetic issue, not a correctness issue. The `id` field is always authoritative.

---

### Revised Gap Summary

| Gap | Decision | Design Pattern | Principle |
|-----|----------|---------------|-----------|
| **Pagination** | `.list()` returns page, `.list_all()` returns lazy iterator | Iterator | Least Surprise |
| **Sync/Async** | Two clients (`VtfClient`, `AsyncVtfClient`), shared entity layer | Strategy | Interface Segregation |
| **Real-time (SSE)** | Core event emitter + `@vtf/sdk-react` adapter for cache sync | Adapter, Observer | Dependency Inversion |
| **Link model** | Discriminated union with `InternalRef` / `ExternalRef`, shared `.display_name` | Polymorphism | Liskov Substitution |
| **MCP tools** | ORM queries + v2 serializers (no SDK, no HTTP-to-self) | Shared Kernel (DDD) | DRY, Uniform Interface |
| **Bulk operations** | Domain-specific bulk methods, not generic batch framework | — | YAGNI |
| **Testing** | Protocol + MockVtfClient + entity factories (three levels) | Dependency Injection | Dependency Inversion |
| **Write side** | Named transition methods, return updated entity, domain exceptions | Command | Replace error codes with exceptions |
| **Authentication** | Pluggable auth strategy, token as default | Strategy | Open/Closed |
| **Schema** | Hand-written SDK, OpenAPI spec for CI validation | — | Stripe pattern |
| **Authorization** | Server-computed `_permissions` object, typed auth exceptions | Tell Don't Ask | Single Source of Truth |
| **Immutability** | Frozen dataclasses, mutations return new instances | Value Object (DDD) | Referential transparency |
| **Nullable refs** | Always present, JSON `null` for unset, never omitted | — | Explicit over implicit |
| **String ID resolution** | Batch lookup for agent/user refs, degraded ref as fallback | Batch Loading | N+1 prevention |
| **URL routing** | Same viewsets, `VersionedSerializerMixin`, DRF `URLPathVersioning` | Template Method | DRY |
| **SDK versioning** | Semver, lenient input builder, no crash on unknown fields | — | Forward compatibility |
| **`?expand=` + lazy** | Expand pre-populates cache, fallback to lazy fetch | Cache-aside | Optimization hint |
| **Staleness** | Accepted for display names, eventual consistency via refetch/SSE | — | Eventual consistency |
