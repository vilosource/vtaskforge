# WC-1 — Workgraph Composition contract (vtaskforge) — DESIGN

**Status:** IMPLEMENTED v0.2 — 2026-05-19. Forks ratified (F-A
server-derived base_ref; F-B milestone select_for_update + 'integrating';
OAQ-7 deferred). C1–C4 delivered north-star TDD on
`feat/wc1-composition-contract`; full suite green. Deploy deferred to a
home session (office cannot reach the cluster).
**Architecture:** R-slice WC-1 of `agentic-pipeline-ARCHITECTURE.md`
§10 (Workgraph Composition substrate). **Kind:** feature (north-star
TDD; system-of-record contract change — same per-merge gate as R2).

## What WC-1 owns

The system-of-record half of the integration-branch model. WC-2 (vafi)
does the git mechanics; WC-1 supplies the *facts and serialization* the
controller consumes. Grounded in source (`workplans/models.py`,
`projects/models.py`, `tasks/services.py`, vafi
`worksources/vtf.py:get_repo_info`).

## Grounded current state

- The DAG grouping unit is the **Milestone** (`workplans.Milestone`,
  `project_filter_path="workplan__project_id"`, status incl. `active`).
  There is no separate "workgraph" entity — a workgraph *is* a
  milestone's task DAG.
- `depends_on` ordering is already server-enforced
  (`resolve_dependencies` / `get_tasks_with_unresolved_deps`).
- The controller resolves the clone branch **per project, not per
  task**: vafi `get_repo_info(project_id)` →
  `RepoInfo(branch=project.default_branch)`. This is the exact thing
  WC-1 must make per-task.
- Idiomatic serialization already in the codebase:
  `tasks/services.py:192` `with transaction.atomic(): … select_for_update()`
  (claim path). WC-1 reuses this idiom — no new locking technology.

## Contract (the three facts WC-1 adds)

### C1 — Milestone-owned integration branch (the fact)
Add `Milestone.integration_branch: str` (blank default). When a
milestone with ≥2 tasks **or any `depends_on` edge** is activated, set
it to `vafi/wg-<milestone_id>`. vtaskforge only records the **name**;
the controller (WC-2) creates/locates the actual git ref off
`project.default_branch` (idempotent) — the R0 split: SoR owns the
fact, controller owns git I/O. Single-task milestones leave it blank ⇒
base_ref falls back to `project.default_branch` (today's behaviour
unchanged — V16).

### C2 — Server-derived per-task `base_ref` (the rule lives in the SoR)
Expose `base_ref` on the task API (v2 task serializer + a
`tasks.services` resolver), derived server-side:
`task.milestone.integration_branch or project.default_branch`. The
controller consumes it (WC-2 changes `get_repo_info`→ per-task
`base_ref`); it never re-derives the rule. Single source of truth,
consistent with R2/OAQ-2 (SoR owns invariants).

### C3 — Serialized merge point + `integrating` state
New task status **`integrating`** (transition
`pending_completion_review`→`integrating` on judge-approve for a task
whose milestone has an integration branch; non-workgraph tasks keep
going straight to `done`). The controller, to take the merge slot,
calls a vtaskforge action that does
`with transaction.atomic(): Milestone.objects.select_for_update()` —
**one in-flight `integrating` task per milestone**; others wait. On
controller report: success ⇒ `integrating`→`done`; conflict ⇒
`integrating`→`needs_attention` (I2, carrying the conflict) ⇒ bounded
rework. State-machine edges added; `done` guard (I4) extended: a
workgraph task may only reach `done` via a recorded successful
integration.

### C4 — Workgraph-scope liveness (I2 at DAG granularity)
Extend the reaper family (sibling of `expire_stale_claims` /
`expire_stale_reviews`): a task stuck in `integrating` past a lease →
`needs_attention` + `integration_expired` event. Closes the new silent
non-terminal that C3 introduces. (A *whole-DAG* stall — every leaf
blocked — is detectable but out of WC-1 scope; flag OAQ.)

## Forks (recommended — light ratification, R2-style)

- **F-A base_ref exposure:** server-derived on the task API
  (recommended — SoR owns the rule, controller consumes) vs
  controller-derived. *Rec: server-derived.*
- **F-B serialization primitive:** `select_for_update()` on the
  Milestone row + `integrating` status (recommended — reuses the exact
  `claim_task` idiom, zero new locking tech, no speculative model) vs
  PG advisory lock vs a dedicated MergeLock model. *Rec: milestone
  select_for_update + `integrating`.*
- **OAQ-7:** whole-DAG deadlock detection + integration-branch GC +
  workgraph-complete→PR-to-`main` automation (defer; first cut:
  controller opens the PR, human merges — irreversible step stays
  human, consistent with merge-ack discipline).

## Files touched (scope fence)

`workplans/models.py` (+`integration_branch`, +migration);
`workplans` milestone-activate path (set the branch name);
`tasks/models.py` (+`integrating` status), `tasks/state_machine.py`
(+edges, +I4 guard), `tasks/services.py` (+`base_ref` resolver,
+take-merge-slot action under milestone `select_for_update`),
`tasks/celery_tasks.py` (+`expire_stale_integrations`), v2 task
serializer (+`base_ref`), settings (beat + lease). Tests at every
level. **Not** touched: the claim path's existing deps logic; humans;
single-task behaviour (must be byte-identical — V16).

## Test plan (north-star TDD, red first)

- Unit: `base_ref` resolver (milestone-with-branch ⇒ integration
  branch; without ⇒ project default; no-milestone ⇒ project default).
- Unit: state machine — new `integrating` edges valid; `done` guard
  rejects a workgraph task that didn't integrate; non-workgraph
  unchanged.
- Integration: two tasks contending the milestone merge slot —
  `select_for_update` serializes (one `integrating` at a time).
- Unit: `expire_stale_integrations` reaps a stale `integrating` →
  `needs_attention` + event; fresh untouched; no cross-talk with the
  claim/review reapers.
- Contract: v2 task payload carries `base_ref`; migration clean
  (`makemigrations --check`); **single-task path byte-identical**.
- Scenario: deferred to the proving delivery (server+client+poetry)
  once WC-2 lands.

## Migration / compat

Additive: nullable/blank `integration_branch`, new optional
`base_ref` (defaults to project default ⇒ today's behaviour), new
status only entered by workgraph tasks. Existing single-task flows and
humans unaffected. Backfill: none needed (no active workgraphs use it
yet).
