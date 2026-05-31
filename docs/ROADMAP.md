# vtaskforge / VFSF ROADMAP — The Ingest Cycle

> **Status:** Living direction doc. Created 2026-05-31. This is the **front door**
> for "where vtf / the ViloForge Software Factory is going next." It supersedes
> `WORKPLAN.md` (which tracked the now-complete Phases 0–7).
>
> **Scope:** VFSF-wide (vtf is the orchestration hub; the cycle also touches
> vafi and introduces a new product, **vtfkb**). This is a *roadmap*, not a
> design — it states goals, sequence, and gates. Each item gates into its own
> DESIGN → IMPLEMENTATION-PLAN before any code.

---

## Where we are

The **Execution Engine is mature and proven.** Phases 0–7 complete; v2 API +
SDKs deployed; MCP redesigned; user management, fleet-principal auth,
review-phase leases, WC-1 composition contract, the R6 spec-admission gate, and
the C.3 variables substrate are all **shipped and live**. Give the execution
engine a high-quality spec and it delivers verified code with near-zero rework.

The **Ingestion Engine does not exist.** This was already named as the gap in
[`design/work-pipeline-ARCHITECTURE.md`](design/work-pipeline-ARCHITECTURE.md)
(two-engine framing; ingestion "operationally unadopted") and
[`backlog-to-execution-gap-ANALYSIS.md`](backlog-to-execution-gap-ANALYSIS.md).
**This cycle builds it.**

---

## The problem this cycle solves

Spec quality is the single biggest determinant of factory output, and producing
a high-quality spec is the one step still done by a human (hand-authored specs or
the `vtf-architect` skill driven turn-by-turn). That human is the bottleneck on
running the fleet unattended. **This cycle turns "a human has an idea" into
"validated, executable specs" as an in-product, agentic pipeline** — human in the
loop where judgment is cheap (the front), out of the loop during execution.

Full problem statement + design brainstorm:
`~/KB/ViloForge-PRD/vfsf-ingest-and-vtfkb-DESIGN.md` (in the ViloForge-PRD repo)
— **BRAINSTORMING, not final.**

---

## Stable base (DONE — do not rebuild)

Execution Engine: state machine, exec→judge loop, spec-admission gate (R6),
variables substrate (C.3), MCP/SDK, fleet-principal auth, review-phase leases,
WC-1 composition contract, console/architect chat widget (live). These are
**records, not direction** — see `docs/design/` and `docs/design/archive/`.

---

## Pre-requisite (carried, gated — not part of the three, but blocks unattended ingest)

- **vafi graceful-shutdown + startup-reconcile of orphaned `doing` tasks.**
  SIGTERM doesn't release a claim; startup doesn't resurface stranded `doing`
  tasks. Ingest will run the fleet unattended, so this reliability gap must close
  first. (= the cloud-native compute-died→requeue pattern; backend-agnostic.)
  *Not started; user-gated.*

---

## The Cycle — three things, in dependency order

> #3 is the **foundation** (#1 seeds it, #2 reads/writes it continuously). Each
> item: **ROADMAP → DESIGN → IMPLEMENTATION-PLAN → build.** Nail down design
> before implementation plans.

### 1. vtfkb — the shared knowledge substrate *(FOUNDATION — design first)*
A new **Python** knowledge-base product (mykb as design reference only). The
shared memory the factory's specialized agents (architect, PM, executor, judge)
collaborate through.
- Per-project repo-local brain (`.vtfkb/`) + a global tier (shared instance).
- mykb-shaped entries (facts/decisions/gotchas/patterns/links) **+ role
  attribution**; JSONL + SQLite + git; `merge=union` for conflict-free appends.
- Brain on `main`; writes split by origin (architect→`main`,
  executor/judge→task-branch→merge); reads branch from `main`.
- Reads: agents-via-`kb`, humans-via-agent (no central mirror on critical path).
- MCP-first + thin CLI; wired into agent pods (architect) and the controller VM
  (executor/judge).
- **Status:** design brainstorm captured; DESIGN not finalized.

### 2. Project Initialization — onboarding (human-interaction layer)
The Project *API* exists; this is the human-facing onboarding that produces a
fully-populated project context (the contract #3 stores and #2 reads).
- **Greenfield** → deterministic UI wizard (declare inputs; provision repo +
  scaffold + empty vtfkb brain skeleton + main doc).
- **Brownfield** → agentic `/init` that explores existing code and seeds the
  brain (analogous to Claude Code `/init`).
- Requires extending the thin Project model (kind greenfield/brownfield, tech
  profile, onboarding status, context link). Input design:
  [`design/project-and-repository-model-DESIGN.md`](design/project-and-repository-model-DESIGN.md).
- **Status:** not designed.

### 3. Ingest Engine — the ongoing human↔agent capture loop
Operates on an **existing, onboarded** project (project-first, not the Apr-05
idea-first framing). Turns a request into validated tasks:
triage → structured-capture / PM elicitation → architect decomposition →
gates → hand tasks to the execution engine.
- The transport already exists (project-scoped architect chat: widget → vafi
  bridge → Pi+Claude pod). Missing: the **methodology** (structured capture),
  the **artifacts** it emits into vtfkb, and architect→SDD-spec→task automation.
- PM / Architect / brownfield-`/init` become **new vafi agent roles** alongside
  executor/judge.
- **Status:** least crisp; design after #1 and #2 are shaped.

---

## Out of scope this cycle

- **Cloud-native execution backend** (bare-VM / AWS) — FUTURE; staying on k3s.
  See `~/KB/ViloForge-PRD/vafi-cloud-native-redesign-DESIGN.md`. Standing rule:
  *consider the cloud-native plan on every vafi change; keep core
  backend-agnostic; don't build the ExecutionBackend seam yet (one-impl
  anti-pattern).*
- Real-time cross-task "hot gotcha bus" — eventual-consistency-via-merge for v1.

---

## Open backlog to triage (not in the cycle; fold in or drop)

- `mcp-cli-improvements-PLAN.md` — unbuilt MCP friction fixes (workplan_id on
  create, milestone CRUD via MCP).
- `mcp-e2e-testing-PLAN.md` — MCP protocol-level E2E (no automated protocol test
  exists today).
- `proposals/session-record-write-api-PROPOSAL.md` — small; bridge audit trail.
- `proposals/agent-pool-manager-PROPOSAL.md`, `proposals/scrum-master-agent-PROPOSAL.md`
  — unbuilt; may feed ingest-era orchestration — re-evaluate against the cycle.

---

## Open design forks (resolve during DESIGN — see the brainstorm doc §8)

1. Global-tier transport: shared **git brain repo** vs **vtf-served API**.
2. Project-context shape: typed entries (leaning) vs single requirements doc.
3. The "fully-onboarded project" schema, field by field (#1↔#2 contract).
4. `.vtfkb/` dir name + confirm Python.
5. Whether architect-to-`main` design writes get a lightweight review gate.
</content>
