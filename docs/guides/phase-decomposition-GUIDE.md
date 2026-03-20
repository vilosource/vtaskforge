# Phase Decomposition Guide

How to go from a design document or project idea to a set of phases ready for task breakdown. This is the step before [task-breakdown-GUIDE.md](task-breakdown-GUIDE.md).

## The input

You have one of:
- A design document describing what to build
- A feature request or problem statement
- An existing system that needs changes
- A rough plan in your head

The output is an ordered set of phases, each with a clear goal, that can be imported into vtf and executed by agents.

## What is a phase?

A phase is a **deployable increment** — after completing it, the system is in a better state than before. It should be:

| Property | Guideline |
|----------|-----------|
| **Self-contained** | The system works after this phase, even if later phases are never done |
| **Sized right** | 5-15 tasks, completable in 1-3 sessions |
| **Testable** | You can verify the phase is done without starting the next one |
| **Ordered by risk** | High-risk or foundational work comes first |

If a phase has 20+ tasks, split it. If it has 2-3 tasks, merge it with an adjacent phase.

## Step 1: Identify the layers

Most projects have natural layers. Read your design doc and identify which of these apply:

| Layer | Examples | Typical phase order |
|-------|----------|-------------------|
| **Foundation** | Project setup, DB schema, core models | First |
| **Infrastructure** | Auth, background jobs, messaging, caching | Early |
| **Core logic** | Business rules, state machines, domain services | Middle |
| **Integration** | External APIs, bulk operations, import/export | Middle |
| **Interface** | CLI, web UI, API polish | Later |
| **Polish** | Bug fixes, performance, UX improvements | Late |
| **Operations** | Deployment, monitoring, documentation | Last |

Not every project has all layers. Some projects are entirely UI work. The point is to find the natural groupings in your specific design.

## Step 2: Find the dependency order

Ask for each layer: **"Can I build this without the others being done?"**

Draw the dependency graph between layers:

```
Foundation → Core logic → Integration → Interface → Polish
              ↓
           Infrastructure
```

Layers that don't depend on each other can be parallel phases. Layers that form a chain become sequential phases.

## Step 3: Split layers into phases

A single layer might become multiple phases if it's too large. Split when:

- **Different deployment targets**: backend API vs frontend SPA → separate phases
- **Risk boundaries**: the risky part should be its own phase so you can validate before building on top
- **Natural milestones**: there's a point where something is usable, then a point where it's polished
- **Team boundaries**: if different agents/people would work on different parts

### Splitting heuristics

| Signal | Action |
|--------|--------|
| Layer has 20+ tasks | Split into 2-3 phases by sub-concern |
| Layer touches both backend and frontend | Split into API phase + UI phase |
| Layer has a "core" part and "extras" | Phase 1: core, Phase 2: extras |
| Part of the layer is risky/uncertain | Isolate the risky part as its own phase |

## Step 4: Order the phases

Place phases in execution order following these rules:

1. **Foundation first** — project setup, core models, migrations
2. **Risk-first** — if something might not work, find out early
3. **Value-first** — if two phases have equal risk, do the more valuable one first
4. **Backend before frontend** — APIs must exist before the UI can consume them
5. **Infrastructure when needed** — auth, caching, etc. should arrive just before they're needed, not at the start

## Step 5: Define each phase

For each phase, write:

```markdown
# Phase N — <Short name>

<One sentence: what "done" looks like>

## Deliverables
- Concrete output 1
- Concrete output 2

## Dependencies
- Requires Phase X (reason)

## Risks
- What might go wrong
```

This becomes the `PHASE.md` file in your phase directory.

## Step 6: Validate the decomposition

Before proceeding to task breakdown, check:

- [ ] **No phase exceeds 15 tasks** (estimate — you'll refine during task breakdown)
- [ ] **Each phase is independently deployable** — the system works after each one
- [ ] **Dependencies flow forward** — no phase depends on a later phase
- [ ] **Risk is front-loaded** — the hardest/most uncertain work is in early phases
- [ ] **First phase is small** — get something working fast to build confidence
- [ ] **Last phase is optional** — if you had to stop, the system would still be useful

## Example: vtaskforge decomposition

The vtaskforge design doc described: a Django API, task state machine, agent claiming, review gates, bulk import, CLI, web UI, SSE events, and multiple agent types.

Here's how it was decomposed:

| Phase | Goal | Why this order |
|-------|------|---------------|
| 0 — Project Setup | Django boots in Docker with health endpoint | Foundation — everything needs this |
| 1 — Core Models | All domain models, CRUD, state machine | Can't do anything without models |
| 2 — Auth, CLI, Bulk Import | Authentication, CLI tool, bulk import endpoint | Needed before we can import real data |
| 3 — Polish & Fixes | Bug fixes, stats, SSE, cursor pagination | Clean up before adding UI |
| 4 — Web UI | React SPA with Kanban board, task detail | Backend is stable, now add the interface |
| 5 — UI Polish | Bug fixes, progress bars, pipeline view, phase management | Improve what Phase 4 built |
| 6 — Task Spec Storage | Store full specs in DB, serve via API | Enable agents to read specs without filesystem |
| 7 — Task Detail Page | Full page view, parsed spec rendering, dependency chain | Rich UX for humans reviewing agent work |

Key decisions:
- **Phases 0-2 are sequential** — each builds on the previous
- **Phase 3 exists because Phase 2 had bugs** — better to fix before adding UI
- **Phases 4-5 split backend UI from polish** — get something visible fast, then improve
- **Phases 6-7 emerged from dogfooding** — we discovered the gaps while using vtf on itself

### What changed during execution

The original plan had 5 phases. Phases 6 and 7 were added after dogfooding revealed that task specs weren't accessible via the API and the task detail modal was too cramped. This is normal — the decomposition is a starting point, not a contract.

## Common patterns

### The "bootstrap" pattern
```
Phase 0: Project skeleton (tiny, proves the stack works)
Phase 1: Core domain models
Phase 2: First usable feature
Phase 3+: Iterate
```

Good for greenfield projects. Phase 0 should be completable in under an hour.

### The "backend then frontend" pattern
```
Phase N: API endpoints for feature X
Phase N+1: UI for feature X
```

Good when the API and UI have different complexity or when you want to validate the API shape before building UI.

### The "fix then build" pattern
```
Phase N: Fix bugs/issues from Phase N-1
Phase N+1: New feature
```

Good when you're dogfooding and finding issues. Don't let bug debt accumulate across phases.

### The "parallel tracks" pattern
```
Phase N: Feature A (backend + frontend)
Phase N (parallel): Feature B (independent)
```

Good when features don't share code. Agents can work on both simultaneously.

## Anti-patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| **One giant phase** | 30+ tasks, takes weeks | Split by layer or concern |
| **Phase per file** | Dozens of tiny phases | Merge related work |
| **Frontend-first** | UI built before API exists | Backend first, or API stubs |
| **All polish last** | 5 phases of features, then 1 phase of bug fixes | Fix bugs between feature phases |
| **Rigid plan** | Refusing to add/change phases based on learnings | Treat the plan as a living document |
| **No Phase 0** | Jump straight into complex work | Always start with a tiny bootstrap phase |

## After decomposition

Once you have your phases defined:

1. Pick the first phase
2. Follow the [task breakdown guide](task-breakdown-GUIDE.md) to decompose it into tasks
3. Write YAML spec files for each task
4. Import into vtf: `vtf import phases/<name>/ --workplan <id>`
5. Execute, learn, adjust the plan for subsequent phases

You don't need to break down all phases upfront. Decompose one phase at a time — learnings from earlier phases will improve later ones.
