# Scrum Master Agent — Proposal

Status: Idea (2026-03-19)

## Context

vtaskforge models a development team:

| Real team role | System equivalent |
|---|---|
| **Developer** | vf-agents — claims and executes tasks |
| **Project board** | vtaskforge — tracks workplans, phases, tasks, reviews, events |
| **Product owner** | Human — defines workplans, approves tasks, final say |
| **Scrum master** | This proposal — facilitates flow, removes blockers, monitors health |

The scrum master doesn't write code or decide what to build. It ensures the process runs smoothly — noticing problems, nudging actors, and surfacing insights.

## What it does

An autonomous process agent that watches vtaskforge's event stream and takes action to keep work flowing.

### Flow facilitation

| Trigger | Action |
|---------|--------|
| Task stuck in `doing` beyond threshold | Ping agent, check health, reassign if unresponsive |
| Tasks piling up in `pending_start_review` or `pending_completion_review` | Notify reviewer(s) |
| Task moved to `needs_attention` | Triage: route to expert agent or human, suggest resolution (rewrite, split, create prerequisite, escalate) |
| Agent idle + unblocked tasks exist | Signal pool manager to claim |
| Dependency resolved (task done) | Check if downstream tasks are now unblocked, notify pool |
| Task in `changes_requested` with no activity | Nudge assignee or re-triage |

### Health monitoring

| Metric | Purpose |
|--------|---------|
| Cycle time (draft → done) | Is work flowing or stalling? |
| Time in review | Are review gates a bottleneck? |
| Rework rate (changes_requested count) | Are tasks well-defined before execution? |
| Agent throughput | Tasks completed per agent per time period |
| Blocked task count | How much work is stuck? |
| Phase progress | Percentage of tasks done per phase |

### Ceremonies (automated)

| Ceremony | Equivalent |
|----------|-----------|
| **Standup summary** | Periodic report: what was done, what's in progress, what's blocked |
| **Sprint review** | Phase/workplan completion summary with metrics |
| **Retrospective** | Analysis of rework rates, failure patterns, bottleneck trends |

## Architecture

The scrum master agent is a **consumer** of vtaskforge — it reads events and task state, and acts via the same RPC API.

```
vtaskforge event stream
        │
        ▼
┌─────────────────────┐
│ Scrum Master Agent   │
│                      │
│ - Event watcher      │  ←── subscribes to vtf events
│ - Rule engine        │  ←── configurable triggers + thresholds
│ - Action executor    │  ←── calls vtf API (add comments, reassign, notify)
│ - Metrics collector  │  ←── aggregates task_events for reporting
│ - Report generator   │  ←── standup, review, retro summaries
│                      │
│ Notifies:            │
│ - Human (chat, email)│
│ - Pool manager       │
│ - vtf (comments on   │
│   tasks)             │
└─────────────────────┘
```

### Key design principles

- **Read-heavy, write-light** — mostly observes, occasionally nudges. Does not make product decisions (that's the human/product owner).
- **Configurable thresholds** — "stuck" means different things for different workplans. Thresholds should be settable per workplan or phase.
- **Pluggable rules** — the trigger→action mapping should be extensible. New rules without code changes.
- **High-reasoning model** — triage decisions (especially for `needs_attention` tasks) require understanding context, not just pattern matching. This agent needs a capable model.
- **Non-blocking** — if the scrum master agent is down, work continues. It's an accelerator, not a gatekeeper.

## Relationship to the review system

The scrum master agent is NOT a reviewer. It doesn't approve or reject tasks. It notices when reviews are slow and nudges. It notices when tasks need attention and triages. The review system (ReviewPolicy, Reviewer, ReviewDecision) handles the actual approval flow.

However, the scrum master could be the one who **assigns** an expert reviewer agent to a task — "this needs_attention task looks like an architecture issue, routing to the architect agent for triage."

## The `needs_attention` status

This proposal introduces a new task status: **`needs_attention`** — distinct from `changes_requested` (review gate outcome).

- **`changes_requested`**: A reviewer looked at the task/deliverable and wants changes. The task definition or implementation needs rework.
- **`needs_attention`**: The executing agent hit a wall and gave up. Something unexpected happened — missing prerequisite, unclear requirements, environment issue. Needs human or expert triage.

The scrum master agent is the primary consumer of `needs_attention` tasks.

## Open questions

- Does this run as a long-lived daemon or periodic cron?
- Where does it live? Own project, part of vtaskforge, or part of vf-agents?
- Notification channels — Slack, email, web UI alerts, all of the above?
- How much autonomy? Can it reassign tasks or only suggest?
- Should it have its own UI panel on the kanban board?
- Is this a single agent instance or one per workplan?
