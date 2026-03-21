# vtaskforge — GitLab Pipeline Analogy

Status: Reference (2026-03-19)

## Mental Model

vtaskforge's execution model is analogous to GitLab CI/CD pipelines. This is intentional — the patterns are proven at scale and well understood.

## Core Mapping

| vtaskforge | GitLab CI | Behavior |
|---|---|---|
| **Workplan** | Pipeline | The whole execution plan |
| **Milestone** | Stage | Grouping that can depend on other groups |
| **Task** | Job | Individual unit of work, runs in a container |
| **`depends_on` links** | `needs:` keyword | DAG dependencies — start as soon as specific dependencies are met |
| **`needs_review_before_start`** | `when: manual` | Gate — waits for human/reviewer approval before entering pool |
| **`needs_review_on_completion`** | Manual approval gates | Verify output before marking done |
| **Agent claiming a task** | Runner picking up a job | Pull from pool, execute, report result |
| **vf-agents (pool manager)** | GitLab Runner | Execution infrastructure — containers, runtimes |
| **Task status** | Job status | draft/todo/doing/done maps to created/pending/running/success |
| **`needs_attention`** | Failed job | Agent gave up — needs triage |
| **`blocked` (manual)** | `when: delayed` / external dependency | Waiting on something outside the system |
| **Kanban board** | Pipeline visualization | Visual representation of execution state |
| **Scrum Master Agent** | Pipeline notifications / auto-retry | Monitors flow, triages failures |
| **Link system** | `artifacts:`, `dependencies:`, `needs:` | Context passing between jobs |

## Evolution Parallel

GitLab CI went through the same design evolution we're following:

1. **Sequential stages** (early) → Stages ran strictly in order. Simple but slow — independent jobs waited unnecessarily.
2. **DAG with `needs:`** (later) → Jobs declare specific dependencies. Can start as soon as their dependencies finish, not the whole stage. Massive parallelism improvement.
3. **Manual gates** (`when: manual`) → Human approval before proceeding. Critical for production deployments.
4. **Child pipelines** → Decompose large pipelines into smaller ones. Analogous to cross-workplan references.
5. **Rules/conditions** → Dynamic job inclusion based on context. Analogous to our ReviewPolicy interface.

We're starting at step 2 (DAG from day one) with step 3 built in (review gates).

## Where vtaskforge Goes Beyond CI

| Aspect | GitLab CI | vtaskforge |
|--------|-----------|-----------|
| **Context richness** | Script + variables + artifacts | Full work packet: description, acceptance criteria, KB areas, files, docs |
| **Review on completion** | Pass/fail only | Human or expert agent reviews deliverable quality |
| **Triage loop** | Retry or fail | `changes_requested`, `needs_attention`, scrum master triage, task refinement |
| **Agent-assisted refinement** | N/A | Chat with architect agent to improve task before execution |
| **Knowledge integration** | N/A | Tasks link to KB areas — agents load domain context |
| **Multi-runtime** | Runner executors (docker, shell, k8s) | vf-agents runtimes (Claude, Gemini, Pi) |
| **Metrics/observability** | Job duration, pipeline duration | Cycle time, rework rate, review turnaround, agent performance |

## Inspiration Points

Areas where we can draw from GitLab's implementation:

### DAG Implementation
- GitLab resolves the DAG at pipeline creation and computes a "needs" graph. Jobs enter pending state only when their needs are satisfied.
- vtf should do the same: when a task's `depends_on` links are all `done`, the task becomes claimable.

### Runner Architecture
- GitLab Runners poll the coordinator API for available jobs. They register with tags/capabilities so the coordinator can match jobs to appropriate runners.
- vf-agents should follow the same pattern: poll vtf API for claimable tasks, register capabilities (runtime type, model, context window).

### Artifacts and Context Passing
- GitLab passes artifacts between jobs — output of job A becomes input to job B.
- vtf equivalent: a task's commit/MR links become context for dependent tasks. The link system enables this naturally.

### Pipeline Visualization
- GitLab's pipeline graph shows stages as columns, jobs as nodes, with dependency arrows. Status is color-coded.
- The kanban board is our equivalent, but we should also consider a pipeline/graph view for workplans — showing milestones and task dependencies visually.

### Retry and Failure Handling
- GitLab has auto-retry (configurable count), manual retry, and `allow_failure`.
- vtf equivalent: vf-agents handles retries (execution concern), `needs_attention` is "job failed permanently", manual triage replaces `allow_failure`.

### Scheduled Pipelines
- GitLab supports cron-triggered pipelines.
- Future vtf consideration: scheduled workplan creation or recurring task patterns.

## Key Takeaway

vtaskforge is essentially a **CI/CD pipeline system where the jobs are executed by LLM agents instead of shell scripts**, with the addition of human-in-the-loop review, knowledge context, and iterative refinement. This mental model should guide design decisions — when in doubt, ask "how does GitLab CI handle this?"
