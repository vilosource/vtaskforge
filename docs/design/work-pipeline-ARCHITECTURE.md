# Work Pipeline — High-Level Architecture

**Status:** Draft / living document
**Last updated:** 2026-05-10
**Owner:** vtaskforge
**Audience:** anyone reasoning about how work flows through the org

## Purpose

This document is the top-level frame. It names the two engines that make
up the vtaskforge work pipeline, defines the boundary between them, and
points at the lower-level docs that detail each.

It exists because the operational docs (`execution-pipeline-ARCHITECTURE.md`,
`backlog-to-execution-gap-ANALYSIS.md`, `workplan-review-PROTOCOL.md`)
describe *how* each part works, but no document yet says *what the two
parts are* and treats them as separately-evolving systems. That framing
is needed to make investment, sequencing, and ownership decisions —
particularly while one half is mature and the other is still emerging.

## The two engines

The vtaskforge work pipeline is two engines, not one:

```
┌──────────────────────────────────────────────────────────────────┐
│                         vtaskforge                               │
│                                                                  │
│  ┌──────────────────┐    ┌───────────────────────────────────┐  │
│  │                  │    │                                   │  │
│  │    Ingestion     │───►│      Task Execution               │  │
│  │     engine       │    │         engine                    │  │
│  │                  │    │                                   │  │
│  │  observation →   │    │  execution-ready task →           │  │
│  │  execution-ready │    │  completed work                   │  │
│  │  task            │    │                                   │  │
│  │                  │    │                                   │  │
│  └──────────────────┘    └───────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

They share infrastructure (the Task entity, the Link model, the Review
model, projects/workplans/milestones), but they have **different
concerns, different maturity, and different evolution paths**, and
mixing those concerns is what produces the friction we keep hitting.

### Task Execution engine

The downstream half. Takes a task that is already execution-ready and
runs it to completion.

- **Input:** a Task in `todo` with a sufficient spec, acceptance
  criteria, dependencies, and required tags.
- **Output:** completed work — commits, PRs, file edits, reports —
  plus a `done` task with verification artifacts.
- **Workers:** executor agents (today: vafi-controller-driven claude
  pods); judge agents (today: same pods with `judge=true`).
- **Mechanics:** claim → execute → submit → review → done, with
  rework loops via `changes_requested`.
- **State:** built. Heavily worked on. Iterating.
  Reliability work in flight (vafi#4 — rolling-restart claim
  orphaning). Judge quality work ongoing. Not the focus of new
  architectural design.
- **Detailed docs:**
  - `execution-pipeline-ARCHITECTURE.md` — stage-by-stage role definitions
  - `guides/simulation-protocol-GUIDE.md` — execution mechanics
  - `post-deploy-verification-DESIGN.md` — judge + verification
  - `agent-project-membership-DECISION.md` — fleet-wide vs scoped access

### Ingestion engine

The upstream half. Takes raw observations / GitHub issues /
operator requests / retro findings and turns them into
execution-ready tasks.

- **Input:** unstructured signal — a GitHub issue, an operator note,
  a kb gotcha, a retro report, a one-line "the breadcrumbs are
  broken" observation. Variable in granularity, in detail, in audience
  (user-facing vs internal).
- **Output:** Tasks meeting the execution-ready bar — sufficient spec,
  acceptance criteria, codebase-verified file paths, dependencies,
  required tags, milestone assignment.
- **Workers (today):** humans (operator + Claude in conversation).
  Each piece of work flows through human judgement on what to capture,
  what to plan, what to spec.
- **Workers (envisioned):** planning agents — architect, PRD, analyst,
  research — each filling a stage of the ingestion flow, each
  reviewable by a planning judge (human at first; agent later).
- **Mechanics (today, well-documented but lightly adopted):**
  Capture → Organize → Plan → Spec authoring → handoff to Execution.
  Stages 1–4 of `execution-pipeline-ARCHITECTURE.md`.
- **State:** the **data model is fully in place** (status lifecycle
  with `draft` / `pending_start_review` / `needs_attention`; `spec`
  field; `acceptance_criteria`; `needs_review_before_start`; `Link`
  model with `depends_on` / `blocks` / `relates_to` / external types).
  The **lower-level analysis is done**
  (`backlog-to-execution-gap-ANALYSIS.md` identifies the missing
  middle and proposes Workspace + `.vtf/` artifacts). What is
  **missing is operational adoption** — the documented flow has run
  end-to-end exactly once (vtaskforge's own Navigation & Breadcrumbs
  milestone, with notable success: zero rework across 6 tasks). It
  has not yet run for vafi work, viloforge-platform work, or
  cross-repo org work.
- **Where investment goes:** this is the open frontier. Designing,
  adopting, and proving the ingestion engine is the next phase of
  work.

## The boundary between the two engines

The boundary is **the execution-ready task**.

A task crosses from Ingestion to Execution when its status transitions
from `draft` (or `pending_start_review`) to `todo`. That transition is
the contract: anything in `todo` is assumed to be execution-ready by
the downstream engine. Anything not yet in `todo` is still owned by
the ingestion engine.

The execution-ready bar — what makes a task ready to cross the
boundary — is partly specified by existing fields on the Task entity:

- `spec` — the implementation-grade specification (file paths, API
  contracts, code patterns)
- `acceptance_criteria` — testable definition of done
- `required_tags` — which executor can claim this
- `requires` / `Link.depends_on` — what other tasks must be done first
- Optional: `agent_model`, `judge`, `test_command`

…and partly by quality the data model can't enforce: spec accuracy
against the codebase, dependency completeness, milestone fit. That
quality is the **product of the ingestion engine** and is the central
artifact this architecture is organized around.

When the ingestion engine is mature, "moving a task to `todo`" should
be a confident handoff. Today it's frequently a coin-flip — which is
why investment in ingestion has the largest leverage.

## Why this split matters

**Maturity asymmetry justifies separate roadmaps.** The two engines
are at very different points; treating them as one system masks that.
Execution work is hardening; ingestion work is greenfield. They should
be planned and resourced separately.

**Quality is determined upstream.** The
`execution-pipeline-ARCHITECTURE.md` design principle —
*"Invest more in the review agent than the executor — spec quality
determines executor success rate"* — is a statement about the boundary.
The Ingestion engine's output quality dominates the Task Execution
engine's success rate. Hardening the executor while ingestion is
under-invested has diminishing returns.

**Org adoption only happens via the ingestion engine.** Today the org
files GitHub issues and humans do everything in conversation. To make
vtaskforge the canonical work queue — to track our own work and
gradually let executors take over — every piece of work must enter
through the ingestion engine. That is the entry point that needs to
be smooth, fast, and trustworthy.

## What this document does not decide

- The internal mechanics of either engine (covered by lower-level
  docs).
- The ingestion engine's high-level design at a step-by-step level
  (next document — see below).
- Which planning roles to introduce, in what order.
- The methodology format for each role.
- How GitHub issues link to tasks (Link model supports it; convention
  TBD).
- Project topology (one project per repo, per product, per team) —
  decision belongs to whoever owns the projects.
- How `.vtf/` artifacts are written and consumed at the per-repo
  level.

These belong in focused design docs that reference back here.

## What's next

Two near-term design artifacts:

1. **Ingestion engine — high-level design.** What does the ingestion
   engine actually do, end to end? Who runs each step? What is the
   methodology? How does it produce execution-ready tasks
   reproducibly? Where does it live (vtaskforge code, agent
   definitions, repo conventions)? This is the design doc the
   *ingestion* half currently lacks at the high level — the
   counterpart to `execution-pipeline-ARCHITECTURE.md` for the
   downstream half.

2. **First adoption test.** Pick one piece of real work
   (likely vafi#4 — rolling-restart fix — since it's a fresh issue
   with sharp scope) and run it through the existing documented
   ingestion flow end to end: create a vafi project in vtaskforge if
   one doesn't exist, file vafi#4 as a draft observation, plan,
   write `vafi/.vtf/specs/<name>/{spec,plan,tasks}.md`, create a
   workplan + milestone + execution-ready tasks, hand off to executor.
   The point of the run is to surface what the documented flow
   actually feels like in practice, what's missing, what's awkward.

The first design artifact and the first adoption test should be
done in parallel — design informs adoption, adoption pressure-tests
design.

## Related documents

- `execution-pipeline-ARCHITECTURE.md` — the 6-stage pipeline,
  primarily covering the Task Execution engine half
- `backlog-to-execution-gap-ANALYSIS.md` — gap analysis identifying
  the missing middle; proposes Workspace + `.vtf/` artifacts
- `workplan-review-PROTOCOL.md` — formalized review/spec authoring
  protocol (the boundary handoff mechanics)
- `simulation-breadcrumbs-RETROSPECTIVE.md` — the one end-to-end run
  of the documented flow; primary evidence that it works
- `design/v2-api-sdk-DESIGN.md` — Phase 5 v1 sunset, an early
  candidate for ingestion-engine adoption (vtaskforge#7)
