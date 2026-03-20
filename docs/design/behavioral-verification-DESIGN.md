# vtaskforge — Behavioral Verification Design

Status: Design (2026-03-19)

## Prior Art: VFF Behavioral Scenarios

This design is based on the proven pattern from VFF (vilo-forge-factory), where a planning agent produces behavioral scenario YAML files and a Judge Agent evaluates them against running code.

**VFF's approach:**
- Behavioral scenarios are plain-language descriptions of expected behaviors
- A Judge Agent (LLM in a container) probes the running service, reads the code, and produces structured verdicts
- Each verdict includes: pass/fail, reasoning, issues found, code references, evidence
- Two-tier evaluation: fast mechanical pre-checks gate expensive judge evaluation

**Example VFF scenario:**
```yaml
id: crud-happy-path
name: "CRUD Happy Path"
description: "Full lifecycle of creating, reading, and deleting an item"
priority: high
behaviors:
  - "POST /items with {\"title\":\"Test\"} returns 201 and a JSON body with id and title"
  - "GET /items returns a JSON array containing the created item"
  - "DELETE /items/{id} with Authorization header returns 204"
```

Source: `vilo-forge-factory/tests/judge-eval/scenarios/` and `internal/scenario/`, `internal/judge/`

## The Problem

Phase 0 dry run revealed that review discipline breaks down without enforcement. Acceptance criteria written as prose ("health endpoint returns 200 with correct JSON") are:
- Subjectively interpreted by reviewers
- Inconsistently verified (some tasks got thorough review, others got rubber-stamped)
- Not machine-verifiable
- No audit trail of what was actually checked

## The Solution: Three-Layer Verification

Each task carries behavioral specifications that enable automated and human verification.

### Layer 1: Behavioral Spec (Machine-Evaluated)

The task includes a behavioral spec — plain-language descriptions of expected behaviors. Written by the planning agent or human during task creation.

```yaml
# Task: Health endpoint
id: health-endpoint-behaviors
task_id: <task-nanoid>
priority: high
behaviors:
  - "GET /v1/health returns 200 with JSON body containing status and checks fields"
  - "GET /v1/health includes db check that shows 'ok' when database is connected"
  - "GET /v1/health includes redis check that shows 'ok' when Redis is connected"
  - "GET /v1/health returns 503 when database connection fails"
  - "GET /v1/health returns 503 when Redis connection fails"
  - "Response content-type is application/json"
  - "Endpoint requires no authentication"
```

**Key principle:** Behaviors are intent, not implementation. "Returns 200 with JSON body" not "curl -s -o /dev/null -w '%{http_code}' returns 200". This makes them:
- Readable by humans
- Evaluable by a judge agent (which can interpret intent)
- Resilient to implementation variations (different JSON field ordering, etc.)

### Layer 2: Judge Agent Evaluation (Automated Review)

When the executor agent submits a task for completion, a judge agent evaluates the behavioral spec against the actual implementation. This is the automated component of `needs_review_on_completion`.

The judge agent:
1. Receives the behavioral spec + access to the running service + access to the codebase
2. Probes the service (HTTP calls, reads responses)
3. Reads the source code (checks implementation quality, not just behavior)
4. Produces a structured verdict per behavior:

```yaml
verdicts:
  - behavior: "GET /v1/health returns 200 with JSON body containing status and checks fields"
    pass: true
    reasoning: "Endpoint returns {'status': 'healthy', 'checks': {'db': 'ok', 'redis': 'ok'}} with HTTP 200"
    evidence: "curl http://localhost:8000/v1/health returned 200 with expected JSON structure"

  - behavior: "GET /v1/health returns 503 when database connection fails"
    pass: true
    reasoning: "Mocked DB failure by stopping postgres, endpoint returned 503 with db error"
    evidence: "Response: {'status': 'unhealthy', 'checks': {'db': 'error: ...', 'redis': 'ok'}}"
    code_refs:
      - "src/core/views.py:25 — ensure_connection() wrapped in try/except"
```

**Verdict includes reasoning and evidence** — not just pass/fail. This creates an audit trail and helps the human reviewer understand what was checked.

### Layer 3: Human Review (Design Judgment)

The judge's verdicts + the executor's self-report are presented to the human reviewer. The human focuses on what machines can't verify:
- Is the code well-structured?
- Does the approach fit the architecture?
- Are there edge cases the behavioral spec didn't cover?
- Should the spec itself be updated?

The human can:
- **Approve** — all verdicts pass, code looks good
- **Reject** — verdicts pass but implementation is wrong (judge can verify behavior but not design intent)
- **Request changes** — with specific feedback
- **Update the spec** — if the behavioral spec was incomplete

## How This Fits in vtaskforge

### Task Shape Extension

```
Task:
  ...
  behavioral_spec: <inline YAML or link to file>
```

Or via the link system:
```bash
vtf link add <task-id> --doc behavioral-spec.yml
```

### Flow Integration

```
draft ──→ (task has behavioral_spec attached)
       ──→ pending_start_review ──→ (reviewer checks: is the spec complete?)
       ──→ todo ──→ doing ──→ agent submits completion
                              ──→ judge agent auto-evaluates behavioral spec
                              ──→ all pass? ──→ pending_completion_review (human)
                              ──→ any fail? ──→ back to agent with verdict details
```

The judge evaluation happens **between agent completion and human review**. It's a gate:
- If all behaviors pass → human reviewer sees verdicts + code, makes final call
- If any behaviors fail → task bounces back to the executor with the failure details (no human time wasted reviewing incomplete work)

### Verdict Storage

Verdicts are stored as task events:

```
event_type: judge_evaluation
data:
  spec_id: health-endpoint-behaviors
  overall_pass: true
  verdicts: [...]
  judge_agent_id: agent-opus-judge-1
  evaluated_at: ISO 8601
```

Queryable for metrics: "what percentage of tasks pass judge evaluation on first attempt?"

## Spec Detail vs Agent Capability (Revisited)

The behavioral spec also addresses the agent capability issue from Phase 0 findings:

| Agent capability | Behavioral spec role |
|---|---|
| **High (Opus)** | Spec describes intent. Agent figures out implementation. Judge verifies. |
| **Medium (Sonnet)** | Spec is more granular — more behaviors, more specific. Agent has clearer targets. |
| **Low (Haiku)** | Spec includes implementation hints alongside behaviors. Agent follows closely. Judge still verifies. |

The spec quality determines success regardless of agent capability — a well-written spec with clear behaviors gives any agent a fair chance, and the judge catches failures objectively.

## Two-Tier Evaluation (From VFF)

For efficiency, evaluation can be two-tiered:

1. **Fast mechanical checks** — automated tests (pytest, curl checks) that run instantly. If these fail, don't bother with the expensive judge evaluation.
2. **Judge evaluation** — LLM-based evaluation for behaviors that require interpretation, code reading, or design judgment.

This maps to:
- Tier 1: Tasks can have a `test_command` field — a script that must exit 0 before judge evaluation. E.g., `pytest tests/test_health.py`
- Tier 2: Judge agent evaluates behavioral spec

```
agent completes → run test_command → pass? → judge evaluation → pass? → human review
                                   → fail? → back to agent (cheap failure)
```

## Open Questions

- Should the behavioral spec be a first-class field on the task or a link?
- Who writes the spec — the human, the planning/architect agent, or both?
- Should the judge agent be a vtaskforge-internal concept or a vf-agents concern?
- How do we handle behaviors that can't be evaluated automatically (e.g., "code is well-documented")?
- Should verdicts be reviewable/appealable by the executor agent?
