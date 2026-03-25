# Phase 3 Retrospective: Management and Review Tools

## Summary

- 6 tasks (P3.1-P3.5 + G3), 7 commits, 1,797 lines added across 10 files
- 0 reworks, 0 failures, 0 judge rejections
- First parallel execution: P3.1-P3.4 ran simultaneously
- Tests: 895 → 924 backend (+29), CLI steady at 206, total 1,130
- MCP server: 1,254 lines of tools, 1,906 lines of tests (1.5:1 test-to-code ratio)

## What went well

### File-per-tool strategy paid off
Phase 2 retrospective recommended splitting tools across files. All 4 Phase 3 tools went into separate files. Result: P3.1-P3.4 ran in parallel with zero file conflicts on tool/test files. Only conflict point was server.py imports, which resolved cleanly via cherry-pick.

### Skipping judges was the right call
Phase 2 found judges were confirmatory-only on additive tasks. Phase 3 skipped them for P3.1-P3.4, relying on the quality gate (G3). Saved ~6 minutes of judge time with no quality loss — all 924 tests passed at gate.

### Parallel execution worked (mostly)
All 4 executors completed successfully and produced correct code. Wall-clock time ~7 minutes (limited by P3.4 at 435s) vs ~12 minutes sequential. Real speedup despite cleanup overhead.

### Spec quality continued to deliver
Zero reworks across all 6 tasks. Pattern validated across 3 phases: Phase 1 (1 rework in 3 tasks), Phase 2 (0 in 5), Phase 3 (0 in 6).

## What went wrong

### Branch contamination from shared filesystem
All 4 parallel agents shared one working directory. When agent A checked out branch X, agent B's next commit went to branch X instead of branch Y.

Evidence:
- P3.1 committed to P3.4's branch
- P3.3's branch picked up P3.2 and P3.4 commits
- Only P3.2's branch was clean (committed before others switched)

Cherry-pick cleanup worked but is manual, error-prone, and wouldn't scale. **This is the #1 blocker for automated parallel execution.**

### Some executors split work into 2 commits
P3.2 and P3.4 each made separate "register tool in server.py" commits instead of including the import in the main commit. Not a problem, but adds commit noise.

### manage_task tool is over-sized
At 488 lines, it's 4x larger than other tools. Handles 10 different actions in one function. Should have been split into sub-handlers or had each action as a separate spec task. Highest rework risk if changes needed later.

## Process evolution across phases

| Metric | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| Tasks | 3 | 6 | 6 |
| Reworks | 1 | 0 | 0 |
| Parallel | no | no | yes (4) |
| Judge per task | yes | yes | no (gate only) |
| Files per tool | shared | shared | separate |

## Implications for vafi containerized harnesses

### 1. Filesystem isolation is mandatory for parallel execution
The simulation used one filesystem with branches — broke immediately. Vafi containers give filesystem isolation for free. Each executor container has its own `/workspace`. This is the strongest argument for the container model.

### 2. The supervisor loop is fully mechanical
Every cycle: claim → branch → dispatch executor → (judge) → merge → complete → approve. Zero supervisor decisions across 23 tasks. The vafi controller replaces this loop directly.

### 3. server.py merge problem needs auto-discovery
Each tool adds an import to server.py. In parallel, this creates merge conflicts. Solution: auto-discover tools via `importlib` at startup (no manual imports). One-time change, eliminates the conflict class entirely.

### 4. Completion review needs streamlining
Every task: `complete` → `pending_completion_review` → `review --decision approved`. In vafi, judge PASS verdict should automatically trigger approval. Controller flow: executor completes → judge verifies → if PASS, controller approves. No separate review API call.

### 5. Branch management belongs in the controller
Executors should work on pre-created branches in their container. Controller creates branch, mounts volume, dispatches. On completion, controller merges. Executor never runs git branch/checkout/merge.

### 6. Merge queue for parallel results
Controller needs: complete all executors → merge to develop one at a time → resolve conflicts → run gate. Cherry-pick works but sequential fast-forward merge is cleaner with proper isolation.

### 7. Gate-only judge model works for mechanical tasks
Skip per-task judges when `judge: false` or task is purely additive (new file, no modifications). Run full judge at quality gate. Cuts ~40% of agent time without quality loss.

## Concrete recommendations for vafi controller

1. Each executor container gets its own git worktree or clone — never share filesystem
2. Auto-discover MCP tool imports — eliminate server.py conflict class
3. Controller owns branch lifecycle: create → dispatch → merge → cleanup
4. Judge dispatch is conditional: `judge: true` = per-task judge, `judge: false` = gate-only
5. Merge queue for parallel results: sequential merge after all parallel executors complete
6. Auto-approve on judge PASS: verdict → controller approves → no separate review step
7. Executor never runs git operations: works on pre-checked-out branch, commits only
