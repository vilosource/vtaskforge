# Simulation Learnings for vafi

Lessons from 42 tasks across 7 milestones of simulated agent execution (Phases 0-6 of the MCP server project). These findings should guide the design and implementation of the vafi controller.

## Context

The simulation used Claude Code subagents (executor and judge) dispatched by a human supervisor following the simulation protocol. The supervisor's role was purely mechanical — claim, branch, dispatch, merge, complete. This document captures what worked, what failed, and what vafi must handle.

**Stats:** 42 tasks, 1 rework (2.4% failure rate), 4 bugs found only by manual/E2E testing, 1,211 tests at completion.

---

## 1. Spec Precision is the #1 Success Factor

### The evidence

| Phase | Spec detail level | Reworks | Tasks |
|-------|------------------|---------|-------|
| Phase 0 | Medium (function signatures, file targets) | 0 | 8 |
| Phase 1 | Medium (approach described, less pseudocode) | 1 | 3 |
| Phase 2 | High (pseudocode, exact test names, constraints) | 0 | 6 |
| Phase 3 | High | 0 | 6 |
| Phase 4 | High | 0 | 5 |
| Phase 5 | High (with implementation alternatives discussed) | 0 | 7 |
| Phase 6 | High | 0 | 7 |

One rework in 42 tasks. The rework (Phase 1, P1.2) happened on a task with a less precise spec — the executor made a design choice that didn't match the specification's response format.

### What a "high quality" spec contains

Every spec that produced a first-attempt pass had:

1. **Exact file paths** — `create: src/mcp_server/tools/search.py`, `modify: src/mcp_server/server.py`
2. **Implementation pseudocode** — not just "implement search" but the actual function signature, parameter handling logic, error paths
3. **Named test functions** — `test_search_by_status`, `test_search_pagination`, etc. with one-line descriptions
4. **Explicit constraints** — "must call find_claimable_tasks() from services, not query models directly"
5. **References** — "follow the pattern in tools/board.py", "see SPECIFICATION.md section 4.7"
6. **Acceptance criteria** — testable assertions the executor and judge check against
7. **test_command** — the exact command to verify the work

### What this means for vafi

The architect phase (where specs are written) is the most important investment. The controller is just a state machine — the quality is in the specs. An hour spent on precise specs saves hours of rework during execution.

**Open question:** Can an AI architect agent write specs this precise? In our simulation, a human wrote all specs. If vafi needs an architect agent, the quality bar is high — and the architect's output should be reviewed before execution begins.

---

## 2. The Supervisor Loop is 100% Mechanical

### The evidence

Across 42 tasks, the supervisor made **zero judgment calls**. Every cycle was:

```
claim → create branch → dispatch executor → (optionally dispatch judge) → merge → complete → approve
```

No task required the supervisor to make a design decision, resolve an ambiguity, or override an executor/judge recommendation.

### What this means for vafi

The controller is a state machine, not an AI agent. It does not need Claude or any LLM. It needs:
- A task queue (vtf API provides this)
- Branch management (git operations)
- Container orchestration (k8s API)
- A merge queue (sequential merge after parallel execution)
- Event-driven state transitions (executor done → dispatch judge → judge pass → merge → complete)

---

## 3. Filesystem Isolation is Mandatory for Parallel Execution

### The evidence

Phase 3 attempted parallel execution with 4 agents sharing one filesystem. All 4 executors produced correct code, but branch contamination caused commits to land on wrong branches. Cherry-pick cleanup worked but was manual and fragile.

Root cause: `git checkout` is a global operation on a shared working directory. When agent A checks out branch X, agent B's next commit goes to branch X.

### What this means for vafi

Each executor container gets its own filesystem. This is automatic with containers — each has its own `/workspace` with a clean clone or worktree. The contamination problem disappears.

**Controller responsibility:** Create a branch, prepare the container's working directory on that branch, dispatch the executor. On completion, extract the commits and merge.

---

## 4. Judge Dispatch Should be Conditional

### The evidence

| Phase | Judge per task? | Issues found by judge | Real value |
|-------|----------------|----------------------|------------|
| Phase 1 | Yes | 1 (P1.2 format issue) | Yes — caught a real problem |
| Phase 2 | Yes | 0 across 5 tasks | Low — all confirmatory |
| Phase 3 | No (gate only) | N/A — gate caught everything | Gate sufficient |
| Phase 4-6 | No (gate only) | N/A | Gate sufficient |

When tasks follow an established pattern (e.g., "add another MCP tool following the same structure as the previous 4"), the judge adds ~60-90 seconds per task for confirmatory value only.

### When to judge

| Scenario | Judge? | Why |
|----------|--------|-----|
| First task establishing a pattern | Yes | No prior reference to validate against |
| Task modifying existing code | Yes | Regression risk |
| Task with complex state transitions | Yes | Logic errors harder to spot |
| Task adding new file following established pattern | No | Pattern already validated |
| Task that is purely additive (new tests, new docs) | No | Low risk, gate catches regressions |

### What this means for vafi

The `judge: true/false` field in the task spec should control whether the controller dispatches a judge. The quality gate task at the end of each milestone always gets a judge. This cuts ~40% of agent time without quality loss.

---

## 5. Four Classes of Bugs and How to Catch Them

### The evidence

| Bug class | Example | Caught by unit tests? | Caught by protocol tests? | Caught by E2E? | Caught by manual smoke? |
|-----------|---------|----------------------|--------------------------|-----------------|------------------------|
| Logic errors | Wrong response format | Yes | Yes | Yes | Yes |
| Async safety | Django SynchronousOnlyOperation | No (969 tests missed) | Yes | Yes | Yes |
| Deployment config | DNS rebinding 421, double-import | No | No | Partially | Yes |
| Integration gaps | Task.DoesNotExist not caught | No | No | Yes | Yes |

### What this means for vafi

The vafi project needs four layers of testing:
1. **Unit tests** — catch logic errors (fast, cheap, run on every commit)
2. **Protocol tests** — catch async/transport issues (medium speed, run on every commit)
3. **E2E tests** — catch integration gaps (slower, run on milestone completion or nightly)
4. **Deployment tests** — catch config/networking issues (slow, run before release)

The E2E pattern from Phase 6 (isolated docker compose, dual MCP+REST verification) is directly reusable for vafi integration testing.

---

## 6. Merge Strategy for Parallel Execution

### The evidence

| Strategy | Used in | Outcome |
|----------|---------|---------|
| Sequential branch → fast-forward merge | Phases 1, 2, 4, 5, 6 | Clean, no conflicts |
| Parallel branches → cherry-pick | Phase 3 | Worked but required manual cleanup |

### What this means for vafi

**Merge queue pattern:**
1. All parallel executors complete on their own branches
2. Controller merges branches to develop **one at a time**, in dependency order
3. If merge conflict: retry with updated base, or escalate
4. After all merges: run quality gate

The controller must never merge in parallel — that creates the same contamination problem.

**Shared file detection:** Any file that multiple parallel tasks modify is a parallelism killer. The controller should detect this during planning (compare `files.modify` across parallel tasks) and either serialize those tasks or accept the merge conflict risk.

---

## 7. Auto-Discovery Eliminates Conflict Classes

### The evidence

Phase 3's only merge conflict was `server.py` — every tool task added an import line. Phase 4 replaced manual imports with auto-discovery (`pkgutil.iter_modules`). Phase 5+ had zero merge conflicts on server.py.

### What this means for vafi

When designing systems that agents will extend, prefer auto-discovery patterns over manual registration. This applies to:
- Plugin/tool registration (auto-import modules from a directory)
- Test discovery (pytest already does this)
- Configuration (env vars or config files over code changes)

---

## 8. The Completion Review is Overhead in Automation

### The evidence

Every task went: `complete` → `pending_completion_review` → `review --decision approved`. The supervisor always approved immediately after reading the judge verdict. Zero rejections at the review stage (rejections happened at the judge stage).

### What this means for vafi

**Judge PASS → controller auto-approves.** No separate review API call needed. The controller flow should be:
1. Executor completes → `vtf task complete`
2. If `judge: true`: dispatch judge → judge returns PASS/FAIL
3. PASS: `vtf task review --decision approved` (automatic)
4. FAIL: dispatch rework executor with judge feedback

For `judge: false` tasks: executor completes → controller approves immediately.

---

## 9. What the Controller Must Own

| Responsibility | How it works |
|---------------|-------------|
| **Task selection** | Query `find_claimable_tasks()`, respect dependency order |
| **Branch creation** | `git checkout -b task/<id>` in executor's volume |
| **Executor dispatch** | Start container with spec in prompt, branch checked out |
| **Completion detection** | Read executor exit/completion event |
| **Judge dispatch** | Conditional on `judge: true` — start judge container with spec + executor report |
| **Accept/reject** | Auto-accept on PASS, re-dispatch on FAIL (max 3 attempts) |
| **Merge** | Sequential merge to develop after executor+judge complete |
| **Board update** | `vtf task complete` + `vtf task review --decision approved` |
| **Rework** | New executor with original spec + judge feedback, same branch |
| **Quality gate** | Dispatch gate task after all milestone tasks complete |
| **Parallel coordination** | Merge queue, shared-file detection, dependency ordering |

---

## 10. The E2E Test Pattern is Reusable

### The pattern

```
1. docker compose up (isolated stack, ephemeral DB)
2. Seed known state (project, tasks, agents, tokens)
3. Connect via protocol client (MCP HTTP or REST)
4. Run scenarios (follow available_actions chain)
5. Verify mutations via independent channel (REST API)
6. docker compose down -v (clean teardown)
```

### For vafi

Replace "MCP client" with "vafi controller" and "scenarios" with "dispatch real executor containers":

```
1. docker compose up (vtf + vafi controller + executor image)
2. Seed: project, workplan, milestone, task specs
3. Start controller — it should pick up tasks and dispatch executors
4. Wait for milestone completion
5. Verify: all tasks done, code merged, tests pass
6. Tear down
```

This is the acceptance test for the vafi controller itself.

---

## Summary: The Minimum Viable Controller

Based on 42 tasks of simulation, the vafi controller needs:

1. **A task poller** — find claimable tasks, respect deps
2. **A branch manager** — create/merge/cleanup branches
3. **A container dispatcher** — start executor/judge with the right prompt
4. **A merge queue** — sequential merge after parallel completion
5. **An auto-approver** — judge PASS → approve, judge FAIL → rework (max 3)
6. **A gate runner** — dispatch quality gate after milestone tasks complete

It does NOT need:
- An LLM for decision-making (the loop is mechanical)
- A spec writer (specs come from the architect, not the controller)
- A conflict resolver (merge queue + shared-file detection prevent this)
- A supervisor agent (that's what the controller replaces)
