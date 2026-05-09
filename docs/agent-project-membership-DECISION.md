# Agent project membership — DECISION

**Status:** decision (locks in the strategy for vtaskforge#2)
**Authored:** 2026-05-09
**Closes the gating decision task:** vtf-development task `pRIao-A_vEvi25Od2Bmvm`

## Problem

When an agent registers via `POST /v1/agents/`, vtf creates a User
account behind the scenes (username == agent's nanoid) but does not
add that user to any project. The task-list endpoints filter by
project membership, so the agent's polling silently returns empty
results — no 403, no warning. Discovered on the vtf-e2e canary first
run (2026-05-09): a judge polled `pending_completion_review` for ~10
minutes getting empty results despite tasks being in that state.

For a multi-project factory, requiring an out-of-band membership add
per (project × agent) doesn't scale.

## Decision

**Auto-add the agent's user as a project member at claim time
(`POST /v1/tasks/{id}/claim/` or the equivalent v2 path), if and only
if the agent isn't already a member.**

This is implemented server-side in the claim service path. The
membership add happens in the same transaction as the claim, so an
agent that successfully claims a task is guaranteed to be a member of
that task's project. Subsequent list/poll calls then return non-empty
results normally.

## Why claim-time over the alternatives

Three options were considered:

| Option | Pros | Cons |
|---|---|---|
| **A. Claim-time auto-add (chosen)** | Demand-driven; agents only join projects they actually do work in. No new opt-in surface. Fits the existing trust model: any registered agent that vtf accepts a claim from is by definition trusted to be in that project. | Slightly opaque side effect; admin who looks at members will see entries they didn't add. Mitigated by recording an event with `auto_added=true`. |
| B. Project-level `agents_open: true` flag | Explicit; opt-in per project. | Forgetting the flag reproduces the silent-fail. Two paths to maintain. |
| C. Add at registration time, per project list | Earliest possible; predictable. | Agents register before knowing which projects they'll work on. Forces a wide pre-grant or a per-(agent, project) registration loop. |

A is the smallest delta from current behaviour, and the demand-driven
shape matches how agents naturally discover work (poll claimable →
claim). B and C require operators to remember to do something
correctly; A is correct by construction.

## Implementation contract

The implementation task that follows this decision (vtf-development
task `PFOQKjwTSlycxWBbFbzqk`) must:

1. In `tasks.services.claim_task` (or the v2 equivalent), after the
   claim has succeeded but before returning, ensure the claiming
   user has a `ProjectMembership` record for `task.project`. Use
   `get_or_create` on `(user, project)` so concurrent claims race
   safely.
2. Default role for the auto-created membership: `member`.
3. Record a `TaskEvent` (or analogous audit event) with
   `event_type='auto_membership_grant'` and data including
   `{project_id, user_id, agent_id, source='claim'}` for observability.
4. **Do not** auto-add on poll/list endpoints — those should remain
   pure reads. The grant happens at the moment the agent commits to
   doing the work.
5. Idempotent: re-claiming or claiming a second task in the same
   project must not produce duplicate memberships and must not
   re-emit the audit event.

## Out of scope (explicitly)

- **Auto-removal** when an agent goes offline or is decommissioned.
  Memberships persist; admins can prune via existing member-remove
  flows. We don't garbage-collect.
- **Role escalation.** Auto-adds are always `member`. Owner/admin
  privileges remain manual.
- **Cross-project visibility.** This decision does not change what
  a non-member can see; it changes what an agent becomes after
  claiming.
- **The poll-side silent-fail itself.** Even with auto-add, an
  agent's *first* claimable poll into a never-touched project still
  returns empty (because membership doesn't yet exist). That's the
  intended shape — agents learn about claimable tasks via the
  cluster's overall `claimable` listing, not a per-project drill-in.

## Risks

- **Overgrant from a misbehaving agent.** If an agent claims a task
  it shouldn't, it gains project membership. Mitigation: existing
  `claim_task` already validates capability tags and reject paths;
  this change adds one more thing that depends on those validators
  being correct.
- **Audit-trail noise.** First-claim per (agent, project) emits one
  extra event. Acceptable; it's once-per-pair, not per-claim.

## What this isn't

A solution to the broader silent-fail family. Sibling decisions:
milestone-reset reactivation (vtaskforge#5, fixed e71e2af-equivalent
on vtaskforge develop) and the `Task.requires` type split
(vtaskforge#4, in-flight). All three live under the same theme:
"vtf shouldn't return empty lists when the truthful answer is
'wrong question'." Each gets its own narrow fix.
