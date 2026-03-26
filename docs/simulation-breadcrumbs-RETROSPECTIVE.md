# Retrospective: Navigation & Breadcrumbs Simulation

**Date**: 2026-03-26
**Milestone**: Navigation & Breadcrumbs (7 tasks)
**Outcome**: All 7 tasks complete, zero rework cycles, 117 tests (was 85)

---

## What Went Well

### 1. Review protocol caught real issues before execution
The draft-to-ready review (Phase 2 codebase verification) caught a false assumption in Task 5 — "data already available from parent board context" was wrong. The modal needs 3 additional hook calls. Without verification, the executor would have discovered this mid-implementation and either guessed wrong or stalled.

### 2. Zero rework cycles
All 6 implementation tasks passed judge on first attempt. This is directly attributable to:
- Detailed specs with code snippets and file paths
- Codebase verification ensuring specs matched reality
- Acceptance criteria giving executors clear "done" definitions

### 3. Task decomposition was right-sized
Splitting the original overloaded Task 1 into "foundation" + "migration" was the right call. The foundation task created the building blocks, and the subsequent 5 tasks all executed cleanly against them. No task was too large or too small.

### 4. Quality gate caught integration-level concerns
The gate verified cross-cutting concerns (no inline styles remaining, no broken links, sidebar context wiring) that individual task judges couldn't see. It also established the new test baseline (117) for future milestones.

### 5. Judges added real value
- T4 judge caught that the executor committed to develop instead of the task branch — a process violation the supervisor would have missed
- T6 judge noted the `useWorkplan` hook signature inconsistency (accepts `string` not `string | undefined`) — useful for future work
- Quality gate judge found the legacy `WorkplanList.tsx` with stale links — pre-existing debt, not a regression

---

## What Went Wrong

### 1. T4 executor committed to wrong branch (PROCESS)
The executor for "Fix TaskPage broken links" committed directly to develop instead of its task branch. The judge caught it, and we fixed it by fast-forwarding the branch pointer. But this breaks the branch-per-task isolation model.

**Root cause**: The executor agent's prompt said "Work on branch task/rXwIQq5ik4tMgocUFe2ve" but the agent may have checked out develop instead. The simulation runs all agents on the same filesystem, so a stale checkout from a previous agent persists.

**Impact**: Low in this case (code was correct, just on wrong branch). High in general — if two executors ran concurrently, one could commit on the other's branch.

**Fix for vafi**: Each executor runs in its own pod with its own worktree. Branch checkout is part of the controller's setup, not the executor's responsibility.

**Fix for simulation**: The supervisor should verify the branch is checked out before dispatching. Add a pre-dispatch check: `git branch --show-current` matches expected branch.

### 2. Premature parallel claiming (PROCESS)
We claimed all 5 tasks simultaneously, then ran executors sequentially because they share a filesystem. This meant claim timers were ticking on tasks 3-5 while we waited for tasks 1-2 to complete. The 30-minute claim expiry could have expired on later tasks.

**Root cause**: The protocol says "dispatch multiple executors simultaneously" but the simulation constraint (single filesystem) prevents true parallelism.

**Fix for simulation**: Claim one task at a time, or claim in small batches where you're confident you'll execute within the expiry window. The protocol's parallel section is aspirational for vafi, not achievable in single-machine simulation.

**Fix for vafi**: True parallelism — each executor gets its own pod and worktree. Claims happen at dispatch time, not in advance.

### 3. Test count discrepancies across branches (CONFUSION)
Each branch was forked from develop before other branches merged, so test counts varied:
- T2 (Sidebar): 97 tests (94 baseline + 3 new)
- T3 (Migration): 100 tests (94 baseline + 6 new)
- T5 (ProjectDashboard): 96 tests (94 baseline + 2 new)
- T6 (TaskDetail): 102 tests on branch, executor reported 109 (stale develop had more)

This caused judge confusion — T3's judge noted "executor reported 100 but actual is 97" and T6's judge noted "executor claimed 109 but branch has 102."

**Root cause**: Branches fork from a shared base but each adds different tests. When executors run tests, they see their branch's count. When judges run tests, they may be on a different branch state (develop with more merges).

**Fix for simulation**: Always state the test delta, not the absolute count. "Added 3 tests, baseline was 94 at fork point." Judges should compare against the fork-point baseline, not the current develop count.

**Fix for vafi**: The controller should record the develop baseline at branch creation time and pass it to both executor and judge. The quality gate is the only place that checks the integrated total.

### 4. Sequential execution is slow (CONSTRAINT)
6 implementation tasks ran sequentially: ~15 minutes total for executors + judges. In vafi with parallel execution on separate pods, tasks 2-6 could all run simultaneously after task 1 merges — cutting execution time roughly in half.

**Not fixable in simulation**: This is an inherent limitation of single-machine execution. The simulation protocol already documents this.

---

## Process Gaps Discovered

### 1. No pre-dispatch branch verification
The supervisor creates the branch and tells the executor to use it, but doesn't verify the executor is actually on the correct branch. Need a pre-dispatch or early-execution check.

**Recommendation**: Add to simulation protocol step 5: "Before dispatching, verify `git branch --show-current` matches the task branch."

For vafi: The controller should `git checkout` the branch as part of workspace setup, before the executor agent starts.

### 2. No explicit merge conflict check
After merging T2, we merged T3, T4, T5 without checking for conflicts first. All merges were clean because the tasks touched different files, but the protocol should have a conflict-check step.

**Recommendation**: Add to simulation protocol step 8 (PASS → merge): "Run `git merge --no-commit --no-ff task/<id>` first. If conflicts, resolve before completing. If clean, `git merge --abort` then `git merge task/<id>`."

For vafi: The controller should attempt the merge and handle conflicts — either auto-resolve or fail the task back to the supervisor.

### 3. Claim expiry is too short for simulation
30-minute claim expiry works for automated vafi executors that start immediately. In simulation, we claim manually and then type out agent prompts — the human latency can eat into the window.

**Recommendation**: For simulation, either extend the claim window or claim just-in-time (right before dispatch, not in batches).

### 4. `needs_review_on_completion` adds friction without value in simulation
Every task had `needs_review_on_completion: true`, which meant submit_work → pending_completion_review → approve → done. The supervisor approves immediately after the judge passes, making the intermediate state pointless in simulation.

**Recommendation**: For simulation, set `needs_review_on_completion: false` so submit_work goes straight to done. The judge verdict IS the review. The vtf review step is for a separate human reviewer — in simulation, the supervisor plays both roles.

For vafi: Keep it — the controller should approve/reject based on judge verdict, making the state transition meaningful.

### 5. Branch cleanup is manual and error-prone
We had to force-delete branches (`-D` instead of `-d`) because git's merge detection doesn't recognize merge commits. This is a minor friction but repeated for every task.

**Recommendation**: Use `git branch -D` (force) for task branches after merge, or use `--no-ff` merge consistently so the branch tip is an ancestor of develop.

For vafi: Branch cleanup is the controller's job after merge confirmation.

---

## Metrics

| Metric | Value |
|--------|-------|
| Tasks completed | 7/7 |
| Rework cycles | 0 |
| Judge FAILs | 1 (T4 — branch process, not code quality) |
| Tests added | +32 (85 → 117) |
| Files created | 10 (2 components + 8 test files) |
| Files modified | 8 (pages + App.tsx + CSS) |
| Executor agents dispatched | 7 |
| Judge agents dispatched | 7 |
| Total agent invocations | 14 (+ 4 verification agents in review phase) |

---

## Recommendations for Vafi Transition

### Must-have before vafi can run this workflow

1. **Branch management in the controller** — checkout, verify, merge, cleanup are all controller responsibilities. Executors should never touch git branching.

2. **Baseline tracking per branch** — record the develop test count at fork time. Pass to executor and judge. Only the quality gate checks the integrated total.

3. **Conflict detection on merge** — the controller must handle merge conflicts, not assume clean merges.

4. **Parallel execution with isolated worktrees** — each executor pod gets its own filesystem. No shared state between concurrent executors.

### Nice-to-have

5. **Spec self-containment validation** — before dispatching, verify the spec references files that exist and hooks/components that are importable. Automate what we did manually in Phase 2.

6. **Executor branch discipline enforcement** — the controller should verify the executor's commits are on the correct branch before proceeding to judge.

7. **Adaptive claim windows** — adjust claim expiry based on task complexity (estimated from spec length, file count, etc.).

---

## Key Insight

The review protocol (draft → ready) and the simulation protocol (ready → done) are complementary but address different failure modes:

- **Review protocol** prevents *specification failures* — wrong assumptions, missing dependencies, vague acceptance criteria
- **Simulation protocol** prevents *execution failures* — code bugs, regressions, process violations

Zero rework in this milestone suggests the review protocol is the higher-leverage investment. A well-specified task is hard for an executor to get wrong. A poorly-specified task will require rework no matter how good the executor is.

**For vafi**: invest more in the review agent than the executor agent. The review agent's quality directly determines the executor's success rate.
