# vtaskforge Process Retrospective — Full Analysis

Status: Complete (2026-03-20)
Scope: Milestones 0-3 of vtaskforge development

## Executive Summary

We built vtaskforge — a distributed task execution system for LLM agents — across 4 milestones, 29 tasks, and ~775 tests. The process itself was the primary experiment: iterating on how LLM agents plan, execute, and verify software development work.

**The key finding:** The task spec format and executor agents work well. The orchestration and infrastructure don't. We spent 3 milestones optimizing the wrong thing (specs, gates, contracts) while the actual bottleneck (database durability, supervisor automation) was never addressed until it broke during dogfooding.

---

## What We Built

| Milestone | Tasks | Tests | Focus |
|-------|-------|-------|-------|
| Milestone 0 | 11 | 13 | Project skeleton, Docker, health endpoint |
| Milestone 1 | 12 | 568 | Core models, CRUD, state machine, reviews, events |
| Milestone 2 | 10 | 720 | Auth, claim expiry, bulk import, CLI |
| Milestone 3 | 7 (6 done) | 775 | Fixes, pagination, SSE, CLI polish |
| **Total** | **40** | **775** | |

All 29 code tasks completed on first attempt. Zero retries. Zero escalations from Sonnet to Opus.

---

## What Worked

### 1. YAML Task Specs as Agent Work Packets

The single most valuable invention of the project. A YAML file containing description, files, implementation approach, constraints, references, and acceptance criteria is sufficient for a Sonnet agent to implement a task cold — no conversation history, no context beyond the file.

**Evidence:**
- 29/29 tasks completed from specs alone
- Milestone 3 validated standardized prompts (no hand-crafted glue) — 6/6 first attempt
- Complex tasks (pagination touching every test file, SSE with new endpoint pattern) succeeded

**Why it works:**
- Sonnet-calibrated detail: specific enough to guide (file paths, code patterns) but not so specific it constrains (no full code listings)
- Self-contained: references point to existing files, not to conversation context
- Verifiable: acceptance criteria have concrete commands (pytest, curl)

### 2. Pytest as the Primary Quality Gate

Gate 1 (mechanical tests) was the only gate that consistently caught real issues. Every test failure pointed to a real problem. Zero false positives.

**Evidence:**
- Milestone 1: caught the cross-task regression (1.12 breaking 1.10's test)
- Milestone 3: caught parallel execution interference (3.5 saw 3.4's changes mid-flight)
- Full suite regression (Gate 1b) caught issues that task-specific tests missed

**What this means:** Invest in tests, not in review process. A good test suite is worth more than judges, contracts, and review gates combined.

### 3. Black-Box Testing

The vtf-blackbox-tester agent found real bugs that unit tests missed:
- Resubmit vs submit confusion (tester called wrong endpoint, revealing UX issue)
- Claim tag matching uses request body, not DB (design gap, not bug)
- Integration flow issues (dependency enforcement across review states)

**Why it works:** It tests the system as a consumer would use it, not as a developer would test it. Different failure modes become visible.

### 4. Parallel Agent Execution

When tasks touch different files, parallel execution works:
- Milestone 2: 2.4 (bulk import) || 2.5 (CLI core) — zero overlap
- Milestone 2: 2.6 || 2.7 || 2.8 (CLI commands) — zero merge conflicts
- Milestone 3: 3.1 || 3.2 || 3.3 (three fixes) — different functions in same file, git merged cleanly
- Milestone 3: 3.4 || 3.5 — different apps entirely

**The rule:** If tasks create/modify files in different directories, they can run in parallel. If they share files, sequential is safer.

### 5. Factory-Based Test Infrastructure

Task 2.1 (test factories) paid for itself immediately. Every subsequent task used factories instead of inline setup, making tests shorter and more maintainable.

---

## What Didn't Work

### 1. The Judge Agent (Gate 2)

Used 4 times across 29 tasks. Found 0 bugs. The two valuable runs (task 1.1 curl verification, task 1.5 state machine structural check) could have been unit tests.

**Root cause:** We redefined the judge three times:
- Iteration 0: behavior tester via curl (duplicated pytest)
- Iteration 1: code reviewer checking design alignment (never tested this version)
- Iteration 2: architectural reviewer checking contracts (never invoked)

Each redefinition was theoretical — we improved the concept without running it. By Milestone 3 we skipped the judge entirely because tests were sufficient.

**Verdict:** The judge adds value only for structural verification that tests can't cover (e.g., "does the transition table match the design doc"). For everything else, tests are cheaper and more reliable. Don't make it a mandatory gate.

### 2. Contracts, Patterns, and affected_files

Added in Iteration 2 of the process guide. Never proved their value:
- **Contracts:** No contract was ever violated. We don't know if they'd catch issues because no issue occurred.
- **Pattern templates:** Agents never referenced them. They copied from existing code (which is what patterns aimed to standardize, but the agents did it naturally).
- **affected_files:** Listed in specs but agents didn't systematically check them. The one time it mattered (Milestone 1, task 1.12 breaking 1.10's test), the agent didn't use the field.

**Root cause:** These were anticipatory solutions for problems that hadn't occurred yet. We added complexity to the spec format without evidence it was needed.

**Verdict:** Keep them as optional fields. Don't make them mandatory. If a problem occurs that contracts would have prevented, add them then.

### 3. Human Review (Gate 3)

Auto-approved every single task across all milestones. The process guide says "human reviews design judgment" but in practice, if Gate 1 (tests) passed, nothing was reviewed.

**Root cause:** When one entity is both the dispatcher and the reviewer, review discipline collapses. This was identified in Milestone 0 (Issue #6), acknowledged in every retrospective, and never fixed.

**Verdict:** Either enforce it (blocking gate) or remove it from the process. Pretending it exists while skipping it is worse than not having it.

### 4. Database Wipe During Dogfooding (Self-Hosting Only)

The database was wiped 4 times during Milestone 3. Each wipe destroyed all imported workplan/milestone/task data, auth tokens, and event history.

**Root cause:** A circular dependency unique to dogfooding — vtf's tracking database lives on the same Postgres instance that agents interact with when developing vtf itself. When agents run `pytest` or `manage.py migrate` against vtf's codebase, they affect the same database that stores the tracking data.

**This is NOT a general vtf problem.** In normal use — vtf tracking development of any other project — agents never touch vtf's database. They run tests and migrations against the target project's infrastructure. vtf's database is completely isolated.

**The real lesson:** vtf should be deployed as a service, not co-located with the project it tracks. In production, vtf would run on its own infrastructure. The dogfooding scenario (tracking yourself) is a special case that requires explicit separation (separate Postgres instance or container).

### 5. The Supervisor Gap

The vtf-supervisor agent was created but never invoked. I performed the supervisor role manually throughout:
- Reading task specs and assembling prompts
- Deciding which tasks to parallelize
- Running gates and interpreting results
- Re-importing after DB wipes
- Fast-forwarding completed tasks

**Root cause:** The supervisor is a user agent that can't be dispatched as a subagent. Even if it could, it needs to maintain state across multiple task dispatches — which requires either a long-running session or persistent state.

**Verdict:** The supervisor should be a script or hook, not a conversational agent. It needs to: poll vtf for work, dispatch executors, run gates, update status. That's automation, not conversation.

---

## What We Could Have Done Better

### 1. Dogfood Earlier

We built the CLI in Milestone 2 but didn't dogfood until Milestone 3. If we'd tried `vtf import` in Milestone 2, we'd have discovered the DB wipe issue two milestones earlier.

**Better approach:** After each milestone, run `vtf import` on the next milestone's specs as a smoke test, even if you don't use vtf to track execution yet.

### 2. Skip the Process Optimization Loop

We spent significant time on:
- Milestone 0 retrospective → Iteration 0 process changes
- Milestone 1 retrospective → Iteration 1 process changes
- Deep retrospective → Iteration 2 process changes (contracts, patterns, affected_files)

Most of these changes were never validated. The process guide grew from a simple execution flow to a complex document with contracts, pattern templates, judge policies, and a 7-field task spec template.

**Better approach:** Start with the minimal process (spec + executor + pytest) and only add complexity when a specific failure demands it. We added contracts because of one cross-task regression that pytest already caught.

### 3. Test the Agents, Not Just the Output

We tested whether tasks completed correctly but never tested whether the agents could operate independently:
- Can the supervisor agent read the board and pick the right task?
- Can the executor handle a spec with an error?
- Can the judge produce actionable feedback?
- What happens when an executor fails?

These were all tested for the first time in Milestone 3 (partially) — too late to iterate on agent design.

**Better approach:** Run each agent on a known-good task from a previous milestone before relying on it for new work. This is agent acceptance testing.

### 4. Separate Tracking from Development

vtf's tracking database should never have shared infrastructure with the development database. This is a day-one architecture decision that we missed because we were thinking about the tracking system as software to build, not as infrastructure to operate.

---

## Process Improvements for Future Milestones

### Tier 1: Do Immediately

#### 1. Deploy vtf as a service, not co-located
In production, vtf runs on its own infrastructure — separate from any project it tracks. The DB wipe issue only occurred because we dogfooded vtf on itself, creating a circular dependency. For any other project, vtf's database is naturally isolated. For self-hosting, use a separate Postgres instance or container.

#### 2. Simplify the task spec
Remove fields that didn't prove their value:

```yaml
# Minimal effective spec
id: <milestone>.<sequence>
name: "<short name>"
depends_on: [<task-ids>]
description: |
  <What and why>
files:
  create: [...]
  modify: [...]
implementation:
  approach: |
    <Step-by-step for Sonnet>
  constraints: [...]
  references: [...]
acceptance_criteria: [...]
test_command: "pytest tests/..."
```

Drop: contracts, affected_files, judge field, behavioral_spec, implementation.pattern. Add them back only when a failure demonstrates they're needed.

#### 3. Gate 1b is the only mandatory gate
Full test suite after every task. Everything else is optional. This is what actually catches regressions.

#### 4. Black-box tester after every milestone
Run the full scenario suite as the milestone completion gate. This catches integration issues that unit tests miss.

### Tier 2: Do When Needed

#### 5. Supervisor as automation, not conversation
Build the supervisor as a shell script or Python script that:
- Polls `vtf task list --status todo`
- Reads the task spec YAML
- Dispatches a Claude Code session with the spec
- Runs pytest after completion
- Calls `vtf task complete` or `vtf task fail`
- Loops until no todo tasks remain

This removes the human from the loop entirely for routine execution.

#### 6. Agent acceptance testing
Before relying on a new agent (executor, judge, supervisor), run it on a known-good task from a previous milestone. If it can reproduce the known result, it's ready.

#### 7. Judge for structural verification only
Don't run the judge on every task. Run it when:
- A new architectural pattern is introduced
- The state machine or core logic changes
- You need to verify alignment with a design doc

This is maybe 2-3 times per milestone, not on every task.

### Tier 3: Future Consideration

#### 8. Contracts when integration grows
When multiple teams or systems consume vtf's API, contracts become valuable for preventing breaking changes. For single-developer single-consumer usage, tests are sufficient.

#### 9. Pattern library when patterns diverge
When agents start producing inconsistent code (different error handling approaches, different test styles), a pattern library becomes valuable. For now, agents naturally copy from existing code, which achieves the same effect.

#### 10. Review gates when quality drops
If first-attempt success rate drops below 80%, or if bugs make it past tests, add review gates. Until then, they're overhead.

---

## Metrics Summary

| Metric | Milestone 0 | Milestone 1 | Milestone 2 | Milestone 3 |
|--------|---------|---------|---------|---------|
| Tasks | 11 | 12 | 10 | 7 |
| Tests | 13 | 568 | 720 | 775 |
| First-attempt success | 100% | 100% | 100% | 100% |
| Retries | 0 | 0 | 0 | 0 |
| Escalations | 0 | 0 | 0 | 0 |
| Parallel executions | 1 round | 0 | 2 rounds | 2 rounds |
| Merge conflicts | 0 | 0 | 0 | 0 |
| Judge invocations | 0 | 2 | 0 | 0 |
| Bugs found by judge | 0 | 0 | 0 | 0 |
| Bugs found by tests | 0 | 1 | 0 | 0 |
| Bugs found by black-box | — | — | 2 | pending |
| DB wipes (dogfooding) | — | — | — | 4 |
| Hand-crafted prompts | All | All | All | 0 |
| Standardized prompts | 0 | 0 | 0 | All |

---

## Final Observations

### The process that actually works

```
1. Write YAML task specs (description, files, implementation, constraints, references, tests)
2. Dispatch Sonnet executor with the spec
3. Run full test suite (pytest)
4. If pass → done. If fail → retry once with failure output.
5. After all tasks → run black-box tester
```

Everything else we added — judges, contracts, patterns, behavioral specs, tiered gate policies, review flag cascading, execution logs — is optimization for problems we haven't had.

### The problem we should solve next

Supervisor automation. The supervisor role was manual throughout all milestones. Building it as a script or hook that polls vtf for work, dispatches agents, runs gates, and updates status would close the loop — making vtf a fully automated execution system, not just a tracking board with manual orchestration.

### Design Drift: Tasks Can Be Individually Correct But Collectively Wrong

The import command was implemented correctly per its spec — import a milestone directory. But the spec was written without considering the full workplan model from the design doc. Each milestone import creates a new workplan instead of adding a milestone to an existing workplan.

The design doc says: Workplan → Milestones → Tasks (one project has many milestones). The implementation says: each import creates a new workplan (each milestone looks like a separate project).

This is a different class of failure from blast radius (code changes breaking consumers). This is **design intent drift** — individual task specs that are internally correct but don't compose into the system the design doc describes.

**Root cause:** Specs were written one milestone at a time. Nobody asked "does this task's behavior make sense in the context of the full system design?" The executor implemented exactly what was specified. The specification was the problem.

**Process fix:** When writing specs for features that span multiple milestones or compose into a larger workflow, review the spec against the design doc's system-level model — not just the immediate task's requirements. Ask: "if I run this 5 times, does the result match the design?"

### The meta-lesson

We spent more time designing the process than was warranted by the problems we encountered. The 100% first-attempt success rate across all milestones means either:
1. The tasks were too easy (unlikely — pagination across all endpoints, SSE streaming, atomic claiming)
2. Sonnet is very capable at Django/DRF development from specs (likely)
3. We over-specified the tasks, leaving no room for failure (partially true)

The right response to a 100% success rate is to reduce process overhead, not add more. Simplify the specs, drop the unused gates, and invest in infrastructure (DB durability, supervisor automation) instead of process documentation.
