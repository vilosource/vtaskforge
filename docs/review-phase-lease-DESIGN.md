# Review-Phase Lease & Reaper — DESIGN (R3)

**Status:** DRAFT v0.1 — 2026-05-17. Design-first; not yet implemented.
**Tracking:** vafi#18 (the I2-backstop half). Architecture R3 of
`viloforge-platform/docs/agentic-pipeline-ARCHITECTURE.md` (§5.1).
**Kind:** bugfix (north-star TDD; close a proven gap with the pattern
that already works — no rebuild, no speculative generality).

## Defect (R0-grounded, source-verified)

`tasks/celery_tasks.py:expire_stale_claims` reaps **only**
`status="doing"` tasks with an expired `claim_expires_at` → moves them
to `needs_attention` (60s beat). There is **no equivalent for the
review phase**: a task that reaches `pending_completion_review` but
whose verdict is never recorded sits there forever — the exact vafi#18
silent stall. R2 makes the judge *able* to write a verdict; R3 is the
**I2 backstop** for when it still cannot (judge crash, absence, future
auth regression, network). Per the governing axiom: the system must
never rest in a silent non-terminal state, and that guarantee must be
**server-side**, not dependent on the controller behaving.

`VALID_TRANSITIONS["pending_completion_review"]` is currently
`[done, changes_requested, cancelled]` — **`needs_attention` is not a
legal escape**, so a reaper cannot simply `perform_transition` it there.

## Design (mirror the proven claim-lease pattern)

1. **New state-machine edge.** Add `needs_attention` to
   `VALID_TRANSITIONS["pending_completion_review"]`. Semantics: "review
   lease expired / verdict unrecordable → escalate to the human
   terminal" (the architecture's first-class human-escalation terminal,
   §3). Deliberate and principled, not a loosening.
2. **Review lease field.** Add `Task.review_expires_at` (nullable
   datetime), mirroring `claim_expires_at`. Set it **centrally in
   `perform_transition`** when `new_status == 'pending_completion_review'`
   (= `now + REVIEW_TIMEOUT`), so *every* path into the review state
   gets a deadline (robust vs setting it in one endpoint). Clear/ignore
   on exit (reaper filters by status, so a stale value is harmless).
3. **Reaper — sibling of `expire_stale_claims`.** Add
   `expire_stale_reviews`: `status="pending_completion_review"` AND
   `review_expires_at < now` → `perform_transition(needs_attention,
   trigger_source="system")` + `record_event("review_expired", …)`.
   Same 60s beat entry. Identical shape to the claim reaper (SOLID:
   parallel function, not a special-case branch).
4. **Config.** `REVIEW_TIMEOUT` via settings/env (default: align with
   the claim default — verify `DEFAULT_CLAIM_TIMEOUT_MINUTES`; likely
   30 min). Single source.

## Scope fence (executor R6)

- `tasks/state_machine.py` (one edge), `tasks/models.py` (+ migration
  for `review_expires_at`), `tasks/celery_tasks.py` (+
  `expire_stale_reviews`), settings beat + timeout, `perform_transition`
  set-on-entry. Tests.
- **Out of scope:** generalising "every non-terminal needs a
  deadline+reaper" — `changes_requested` re-enters `doing` (covered by
  the next claim lease); only `pending_completion_review` is the proven
  silent-stall. The generalisation is a noted *forward principle*, not
  built (no speculative generality).
- **Complementary, separate (R3b, vafi side):** controller
  verdict-write failure should also fail-loud (transition the task)
  rather than swallow — defence-in-depth atop this server backstop.
  Filed as follow-up; not in this slice.

## Test plan (north-star TDD)

- Unit (state machine): `pending_completion_review → needs_attention`
  now valid; other transitions unchanged; entering
  `pending_completion_review` sets `review_expires_at`.
- Unit (reaper): a `pending_completion_review` task with
  `review_expires_at < now` → `needs_attention` + `review_expired`
  event; one with a future deadline untouched; a `doing` task untouched
  by `expire_stale_reviews` (and vice-versa — no cross-talk).
- Migration: `review_expires_at` added; `makemigrations --check` clean.
- Regression: full suite green; `expire_stale_claims` behaviour
  unchanged.
- Scenario: covered by the judged Flask experiment regression — with R2
  the judge records a verdict (no reaper fire); a fault-injected
  judge-down run escalates to `needs_attention` within one beat instead
  of stalling forever.

## Migration / compat

Additive: nullable `review_expires_at` (NULL ⇒ reaper ignores; only
tasks that enter the state *after* deploy get a deadline — acceptable;
pre-existing stalled tasks, if any, are handled by ops, not a
back-dated sweep). New beat entry is additive. No behaviour change for
humans or the claim path.
