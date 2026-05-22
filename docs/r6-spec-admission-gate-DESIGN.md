# R6 — Spec-admission gate (MQ-F3) — DESIGN

**Status:** DRAFT v0.1 — design-first, pre-implementation.
**Owner:** lonvilo@pm.me
**Slice:** R6 of the deterministic-substrate roadmap
(`viloforge-platform/docs/agentic-pipeline-ARCHITECTURE.md` §7 item 6;
the input/architect substrate — symmetric to R0–R3 execution substrate).
**Upstream:** MQ-F3 (`vtf-methodologies/spec-author/feature.md:354-357`);
F2 (`feature.md:65-74`); verifier V4/V5/V6/V7 (`verifier/bugfix.md`).
**North star:** `viloforge-platform/docs/engineering-principles.md`.

---

## 1. Problem (source-grounded, verified 2026-05-21)

The executor's deliverable is deterministically adjudicated (the always-
present delivery gate, `vafi/src/controller/gates.py`, + the task's
`test_command`). **The architect's *spec* is not.** Today spec quality is
enforced only by an autonomous verifier-agent + a planning-judge *after*
submission (`spec-driven-adoption-DESIGN.md:412-441`) — an LLM/human
fence. The architect is therefore **self-adjudicated**: the KNOWN AXIOM
GAP (`feature.md:33-41`). An LLM verifier can rubber-stamp; nothing
deterministic prevents an inadmissible spec from reaching the executor.

MQ-F3 (load-bearing, verbatim): *"The spec-admission gate: deterministic
pre-claim check that ACs are machine-checkable, every AC has a labelled
gate assertion (F2), fail-loud present, contract pinned. Until built, the
architect is self-adjudicated (the KNOWN AXIOM GAP)."*

## 2. The recursive insight

R6 is the **recursive image of the delivery gate**. The delivery gate
deterministically checks the *executor's* output (a branch was durably
pushed); R6 deterministically checks the *architect's* output (the spec
is admissible) — same raise/exit-code discipline, applied one layer up.
By the governing axiom (durable, correctness-load-bearing outcomes are
owned by the deterministic layer, never an LLM), spec admission must be a
deterministic seam, not an LLM judgment.

## 3. Where it runs (OAQ-5 RESOLVED — server-side guard)

**vtaskforge owns it, as an `ENTRY_GUARD` on the `todo` transition.**

Grounded basis: vtaskforge already has exactly this machinery.
- `Task` stores the spec structurally: `acceptance_criteria` (JSON list
  of strings), `test_command` (JSON `{command: "..."}`), `spec` (text)
  (`tasks/models.py:54,88,90`).
- The server-side state machine runs **entry/exit guards** inside
  `perform_transition` (`tasks/state_machine.py:150-165`); a guard raises
  `GuardViolation` to block the transition. `guard_has_workplan` already
  blocks entry to `todo` — the exact precedent.
- `todo` is the claimable state (`tasks/services.py:198-199`: claim
  requires `status in (todo, changes_requested)`). Guarding `todo` entry
  = pre-claim, by construction.

Why server-side and not a client/architect-side pre-check: §5.1 ("the
system of record owns its invariants") — a client-only check is the
invariant-in-a-client anti-pattern (any other client could submit an
inadmissible spec, exactly the conflation R2/R3 removed). A pre-submit
CLI check MAY exist later as fast-feedback *convenience*, but the
authoritative gate is the server guard. **This closes the gap in
existing machinery (R3/R4 ethos), it is not a new subsystem.**

## 4. What "admissible" means — the deterministic floor

R6's guard enforces the cleanly-deterministic, field-local subset (the
rest stays with the verifier-agent — see §6). For a task entering `todo`
**that has ≥1 acceptance criterion**:

- **A1 — F2 AC-id coverage.** AC ids are 1-based positional
  (`feature.md:186`): the Nth `acceptance_criteria` item is `AC<N>`.
  Every id `AC1..ACn` MUST appear as a labelled assertion in
  `test_command.command` (the F2 coverage rule, `feature.md:65-74`:
  "every AC has ≥1 labelled assertion; an AC with none is decorative and
  the spec is inadmissible"). An uncovered AC ⇒ reject.
- **A2 — `test_command` non-empty.** `test_command.command` present and
  non-blank (a spec with ACs but no gate is decorative). (V6.)
- **A3 — fail-loud directive present.** The spec body carries the
  canonical fail-loud clause (distinctive signature: *"do not rationalize
  partial completion as success"*, `spec-author/bugfix.md:132-133`).
  (V7/R3.)

Pass ⇒ transition proceeds. Any failure ⇒ `GuardViolation` naming the
specific defect (which AC is uncovered / missing gate / missing
directive), so the architect gets a precise, actionable rejection — the
recursive image of the delivery gate's "branch not found on origin".

### Scope decisions (resolved)

- **OQ-R6a — tasks with zero ACs are EXEMPT.** Bare/manual tasks (no
  `acceptance_criteria`) are not SDD specs and legitimately enter `todo`
  today (e.g. operator one-offs). The guard fires only when the task
  makes machine-checkable claims (has ≥1 AC). Ghost-completion of a
  no-AC task is already backstopped by the always-present *delivery*
  gate (F7/F10 closed in `gates.py`). Mandating ACs on every claimable
  task is a stricter v2 policy, deferred.
- **OQ-R6b — contract-pinning (V18) stays with the verifier.** vtaskforge
  cannot deterministically resolve an external-provider citation
  (file:line in a foreign repo / live OpenAPI) without fetching it; a
  mere "a citation string exists" check is weak and false-reject-prone.
  R6's floor is the three field-local checks above; V18 remains an
  LLM-verifier responsibility. (Faithful application of "don't over-reach
  into fetch/semantic territory".)

## 5. Design — `guard_spec_admissible`

A new guard appended to `ENTRY_GUARDS["todo"]`, beside
`guard_has_workplan` (Open/Closed — no change to `perform_transition`,
`_run_guards`, or other guards):

```python
def guard_spec_admissible(task):
    acs = task.acceptance_criteria or []
    if not acs:                      # OQ-R6a: bare task, exempt
        return
    command = (task.test_command or {}).get("command", "") or ""
    # A2
    if not command.strip():
        raise GuardViolation(task.status, "todo",
            guard_name="guard_spec_admissible",
            message="Spec inadmissible: has acceptance_criteria but empty "
                    "test_command (no machine gate). [A2]")
    # A1 — every AC id AC1..ACn appears as a labelled assertion
    uncovered = [f"AC{i}" for i in range(1, len(acs) + 1)
                 if f"AC{i}" not in command]
    if uncovered:
        raise GuardViolation(task.status, "todo",
            guard_name="guard_spec_admissible",
            message=f"Spec inadmissible: acceptance criteria with no "
                    f"AC-id-labelled gate assertion: {uncovered}. Every AC "
                    f"needs ≥1 labelled assertion in test_command (F2). [A1]")
    # A3 — fail-loud directive present
    if FAIL_LOUD_SIGNATURE not in (task.spec or "").lower():
        raise GuardViolation(task.status, "todo",
            guard_name="guard_spec_admissible",
            message="Spec inadmissible: missing fail-loud directive in "
                    "spec body (V7/R3). [A3]")
```

`FAIL_LOUD_SIGNATURE = "do not rationalize partial completion as success"`
(lower-cased compare; the canonical R3 clause).

Admin `reset` (force-transition) bypasses guards by design — the operator
override, identical to how `guard_has_workplan` is bypassable. Rework
re-entry (`changes_requested → doing`) does not re-enter `todo`, so the
spec is admitted once at first `todo`; the spec text is immutable across
rework, so no re-check is needed.

## 6. What R6 does NOT do

- It does not replace the verifier-agent or planning-judge. It adds a
  deterministic **floor** an inadmissible spec cannot pass regardless of
  LLM rubber-stamping. Semantic checks — V4 "is this AC meaningful beyond
  having a label", V14 pattern coherence, V18 full contract grounding,
  V13 pyramid-coverage judgment — remain LLM-verifier responsibilities.
- It does not mandate ACs on every task (OQ-R6a).
- It does not parse the test_command as an AST — substring presence of
  the `AC<n>` label is the F2 coverage contract (matches how the
  methodology specifies labels and how the executor's gate consumes
  them). AST-level assertion validation is a possible v2 hardening.

## 7. Test plan (TDD red→green, server-side)

Unit (`tests/tasks/test_state_machine.py`), each red→green:
- AC-covered spec (AC1/AC2 both labelled in test_command) + fail-loud +
  non-empty command → `todo` transition **succeeds**.
- AC2 unlabelled in test_command → `GuardViolation` naming `['AC2']` [A1].
- ACs present but `test_command` empty → `GuardViolation` [A2].
- ACs + gate present but no fail-loud clause → `GuardViolation` [A3].
- Zero ACs → transition **succeeds** (OQ-R6a exemption).
- `guard_has_workplan` still fires independently (no regression);
  admin `reset` still bypasses (force-transition unaffected).

Integration: claim path (`services.py`) — an inadmissible spec never
becomes claimable (stays out of the claimable queue because it can't
reach `todo`).

Dogfood (vtf-dev): submit one inadmissible spec (AC with no labelled
assertion) → blocked at `todo` with the precise message; one admissible
spec → reaches `todo`, claimable, runs.

## 8. Blast radius / safety

Pure-function guard over already-stored fields; no new model fields, no
migration, no change to `perform_transition`/`_run_guards`. Exempts the
existing bare-task workflow (OQ-R6a) so no current task regresses (V16).
Admin `reset` override preserved.
