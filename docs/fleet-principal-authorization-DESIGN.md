# Fleet Principal Authorization — DESIGN (R2)

**Status:** DRAFT v0.1 — 2026-05-17. Design-first; not yet implemented.
**Tracking:** vafi#18 (judge silent-stall) + the operator-token-cannot-
grant friction. Architecture R2 of
`viloforge-platform/docs/agentic-pipeline-ARCHITECTURE.md` (§5.3, Bet B
RATIFIED). **Supersedes the *frame* of**
[agent-project-membership-DECISION.md](agent-project-membership-DECISION.md)
(2026-05-09) — see §Reconciliation.
**Kind:** architecture slice (north-star TDD; system-of-record change).

## Problem (source-grounded)

`core/authorization.py` is the entire project-access layer — four
gates, each with a single bypass `user.is_staff`, each else-consulting
`ProjectMembership`:

- `scope_queryset_to_user_projects` (list filtering) — L9-21
- `check_project_membership` / `require_project_membership` — L24-36
- `ProjectScopedPermission` / `RoleBasedPermission` — L39-86

Fleet agents are modelled as project *members*: a registered agent is a
plain `User` (username = agent nanoid), and `claim_task` auto-creates a
`ProjectMembership(member)` for it (the 2026-05-09 decision). The review
path (`reviews/`) has **no** equivalent → the judge agent, never a
member, hits `require_project_membership` → `PermissionDenied: You are
not a member of this project.` → vafi#18 silent stall. `POST
/projects/{id}/members/` is `is_staff`-only, so even the operator token
cannot repair it. A dormant `UserProfile.user_type ∈ {human, agent,
service}` exists and is consulted by **nothing**.

## Reconciliation with the 2026-05-09 decision

That decision chose claim-time auto-add (Option A) over a project flag
(B) and registration-time per-project pre-grant (C). **It reasoned
entirely within the "agents must become ProjectMembers" frame.** Every
hole found since is a leak in that frame, patched within it:

- Executor poll-after-claim: patched by claim-time auto-add.
- Judge review: *no* claim → frame has no hook → vafi#18.
- The decision's own "Out of scope: first-claim poll still returns
  empty" — an admitted, unfixable-in-frame hole.

The instinct was right (*correct-by-construction; no operator-remembered
step; audited*); the **frame is the defect**. Fleet agents are not
project collaborators — they are **deployment infrastructure that serves
every project in the instance**. Modelling infra as per-project
membership is the category error. Option C's rejected con ("per-project
pre-grant doesn't scale") **dissolves** under a role model: there is no
per-project grant at all. This DESIGN supersedes the membership frame
for *fleet principals only*; human membership semantics are unchanged.

## Design

Introduce a second recognised principal class beside `is_staff`: the
**fleet service principal**, recognised via the (now-activated)
`UserProfile.user_type == 'service'`. A fleet principal is authorised
**by role across the instance's projects — without any
`ProjectMembership` row.**

1. **Predicate.** Add `is_fleet_principal(user) -> bool` in
   `core/authorization.py` (true iff authenticated and
   `user.profile.user_type == 'service'`). One source of truth.
2. **Consult it in the same four gates**, beside the `is_staff`
   bypass — but role-bounded, not blanket: a fleet principal passes
   project scoping/membership checks for any project; `RoleBasedPermission`
   grants it the write surface its **fleet role** needs (executor:
   claim + own-task writes; judge: review writes) and nothing beyond
   (no project delete, no membership admin — those stay `is_staff`).
   Role derives from the existing `Agent` capability tags
   (executor/judge), not a new field if avoidable (verify against
   `agents` model in the impl slice).
3. **Activate the seed at registration.** `agents/views.py` agent
   creation sets the backing User's `UserProfile.user_type='service'`
   (idempotent; backfill migration for existing agent users).
4. **Remove the claim-time auto-add hack** (`tasks/services.claim_task`)
   — superseded; keep emitting an audit event on first fleet action per
   (principal, project) for the observability the decision valued.
5. **Humans unchanged.** `user_type='human'` path is byte-for-byte the
   old behaviour. Existing `ProjectMembership` rows remain valid and
   authoritative for humans.

The predicate is the **seam**: tightening scope later (see fork) never
touches the four call sites.

## The one design fork — scope of fleet authority (RATIFICATION)

Architecture OAQ-1/Bet B fixed the *frame* (role, not membership) but
not the *scope*:

- **S1 — instance-wide (recommended).** A fleet principal has its
  role-capability over **all projects in this vtf deployment**.
  Rationale: one vafi fleet *is* the deployment's worker pool (literally
  how vafi-dev runs); this models reality, zero per-project state,
  correct-by-construction. This is *not* a shortcut — it is the honest
  model of the actual system; S2/S3 are speculative until a real
  multi-fleet requirement exists (YAGNI, per the no-hand-patch
  strategy's flip side: also no speculative generality).
- **S2 — fleet-scoped.** A `Fleet` entity; principals belong to a
  fleet; fleet ↔ project-set association. Granular multi-tenant; adds a
  model + association surface.
- **S3 — capability/policy claims.** Authority encoded per-principal by
  explicit policy. Most general, most complex.

Recommendation: **S1 now, behind the predicate seam so S2/S3 are
non-breaking refinements later.** Blast-radius note: a leaked fleet
token can already claim any claimable task instance-wide today; S1 does
not widen the *content* exposure for humans (their scoping is
unchanged). Token hygiene is OAQ-3's concern, not a reason to pick S2.

## Out of scope (fence)

- Human/operator authority model (why the operator token can't add
  members) — a separate human-RBAC question; **not** conflated here.
- Auto-removal / GC of stale principals (unchanged from prior decision).
- Workspace credential identity (OAQ-3). Lease/reaper review-phase
  coverage is **R3** (complementary I2 backstop; designed next).

## Test plan (north-star TDD, when ratified)

- Unit (`core/authorization.py`): `is_fleet_principal` truth table;
  each of the 4 gates — service principal authorised role-bounded with
  **no `ProjectMembership` row**; human path unchanged; viewer/owner
  human semantics unchanged; fleet principal denied membership-admin /
  project-delete.
- Integration (real DRF + Postgres): judge agent (no membership) can
  `POST /v2/tasks/{id}/reviews/` on a fresh project; executor agent can
  claim + write execution_summary with no membership row; human
  non-member still 403.
- Contract: agent registration sets `user_type='service'`; backfill
  migration covers pre-existing agent users.
- Scenario / dogfood: the **Flask experiment on a fresh project**
  reaches a real judge verdict (vafi#18 closed end-to-end) — the
  judged-experiment-runnable milestone.

## Migration / backward-compat

Additive: new predicate + nullable-safe profile access (default
`'human'` ⇒ old behaviour). Backfill `user_type='service'` for existing
agent-backed users in the same migration. Remove the claim-time auto-add
*after* the predicate path is proven (two adjacent commits) so there is
never a window where a fleet agent is unauthorised.
