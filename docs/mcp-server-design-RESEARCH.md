# MCP Server Design Research for vtf

Research findings on Model Context Protocol server design patterns, applied to building an MCP interface for vtaskforge.

## Core Principle

**MCP is a UI for agents, not an API wrapper.**

REST APIs are designed for human developers who read documentation. MCP tools are for LLMs that discover capabilities from descriptions and act through inference. The fundamental anti-pattern is mapping REST endpoints 1:1 to MCP tools — this forces the LLM into multi-step orchestration, wastes context tokens, and increases hallucination risk.

> "Do the orchestration in your code, not in the LLM's context window." — philschmid

## Design Rules

### Do's

1. **Design around outcomes, not operations** — bundle the steps an agent always does together into one tool. If claiming a task always requires checking deps, fetching spec, and getting test commands, that's one tool, not four.

2. **Flatten arguments** — use typed parameters with constrained choices (Literal enums, defaults). Never accept `dict` or nested structures. Agents guess structure and hallucinate missing keys.

3. **Curate ruthlessly** — 5-15 tools per server maximum. Every tool description consumes context window tokens. One server, one job.

4. **Enrich responses with decision context** — don't return raw data. Pre-compute "what can I do next?" and include it in the response. Return task + spec + dependency status + available actions, not just task fields.

5. **Error messages are instructions** — agents treat errors as observations and self-correct. Return actionable guidance: "Task is in 'blocked' status. Available transitions: unblock -> todo. Resolve the blocker first."

6. **Name tools for discovery** — use `{service}_{action}_{resource}` pattern (e.g., `vtf_claim_task`). Generic names like `create_task` collide across services.

7. **Paginate with metadata** — return `has_more`, `next_offset`, `total_count`. Default limit 20-50. Never dump hundreds of records.

### Don'ts

1. **Don't mirror the REST API** — the whole point is to add value beyond what the API provides.
2. **Don't force multi-step orchestration** — if an agent always calls A then B then C, make it one tool.
3. **Don't expose internal IDs without context** — include titles, summaries, human-readable status.
4. **Don't use nested/complex parameter types** — agents hallucinate structure.
5. **Don't return raw errors** — translate API errors into guidance the agent can act on.

## Key Patterns

### Workflow-Based Tools

Bundle multiple API operations into atomic tools that handle complete workflows internally. Instead of exposing `create_project`, `add_environment_variables`, and `create_deployment` separately, combine them into one `deploy_project` tool.

### Layered Tool Pattern (Block/Goose)

Three conceptual layers that reduced 200+ endpoints to 3 tools:

- **Discovery** — agent explores what's available (board state, project overview)
- **Planning** — agent determines what to do next (find claimable work, check priorities)
- **Execution** — agent acts (claim, complete, review)

### Progressive Discovery

Start with high-level tools. Let the agent drill down only when needed. Don't front-load all tool schemas — each consumes 5-7% of context window.

### Error-Guided Recovery

Tools should provide actionable recovery guidance, not raw error codes. A rate-limit error should say "retry after 30 seconds or reduce batch size to 50" not just return a 429.

### Parameter Coercion

Accept multiple input formats and normalize internally. Dates as "2024-01-15", "January 15", or "yesterday" — the tool handles conversion, not the agent.

## Applied to vtf: Proposed Tool Surface

Target: ~8-10 tools organized around agent workflows, not REST endpoints.

| Tool | Purpose | Value Over REST |
|------|---------|-----------------|
| `vtf_board_overview` | Project state summary | Task counts by status + blockers + attention items in one call (replaces 5+ API calls) |
| `vtf_next_work` | Find what to work on | Matches agent tags, resolves deps, returns best candidate with full context |
| `vtf_claim_and_start` | Claim task and get everything needed | Claims + returns spec + deps + test commands — agent is ready to work immediately |
| `vtf_report_progress` | Update during work | Heartbeat + add note in one call |
| `vtf_submit_work` | Finish task | Complete + trigger review if configured + attach output |
| `vtf_search_tasks` | Find tasks by criteria | Enriched results with status context and available actions |
| `vtf_task_detail` | Deep-dive on one task | Full context with spec, deps, reviews, events, and available transitions |
| `vtf_manage_task` | Create/update/transition | One tool with `action` parameter for CRUD and lifecycle operations |

### Response Enrichment Example

Instead of returning raw task JSON:

```json
{"id": "abc", "status": "todo", "title": "Fix auth", "claimed_by": null}
```

Return enriched context:

```json
{
  "task": {"id": "abc", "title": "Fix auth", "status": "todo"},
  "spec_summary": "Implement OAuth2 PKCE flow for mobile clients",
  "dependencies": {"resolved": true, "details": []},
  "available_actions": ["claim", "block", "defer", "cancel"],
  "test_command": "pytest tests/test_auth.py -v",
  "agent_model": "sonnet"
}
```

The agent gets everything it needs in one response to decide and act.

## vtf Backend Readiness

Current state assessment for adding MCP:

**Already extracted (can be called from MCP directly):**
- `tasks/state_machine.py` — transition validation + execution
- `tasks/review_policy.py` — review flag cascade logic
- `workplans/completion.py` — milestone auto-completion
- `core/bulk_import.py` — complex entity creation

**Needs extraction before MCP (logic stuck in views):**
- Task claim logic (~110 lines in views.py) — atomic validation, tag matching, dependency resolution
- Claimable query logic — dependency resolution duplicated from claim
- Review routing — decision-based state transitions
- Event creation — duplicated in 5 places
- Agent upsert — user/token creation

**Recommended approach:** Extract a service layer first, then both REST views and MCP tools become thin adapters over shared services.

## Architecture Options

### Option A: MCP as proxy over REST API

```
LLM -> MCP Server -> HTTP -> Django REST API -> DB
```

- Quick to build, decoupled
- But: network hop, auth token management, no composite query advantage

### Option B: MCP embedded in Django

```
LLM -> MCP Server -> Service Layer -> DB
```

- Direct access to service layer and ORM
- Composite tools can batch queries efficiently
- Single deployment, shared auth
- Requires service layer extraction first

**Recommendation:** Option B. The composite workflow tools (claim_and_start, board_overview) need to batch multiple queries efficiently. Going through HTTP for each sub-query defeats the purpose.

## Sources

- [MCP is Not the Problem, It's your Server](https://www.philschmid.de/mcp-best-practices) — philschmid (2025)
- [Less is More: 4 Design Patterns for MCP Servers](https://www.klavis.ai/blog/less-is-more-mcp-design-patterns-for-ai-agents) — Klavis AI
- [54 Patterns for Building Better MCP Tools](https://www.arcade.dev/blog/mcp-tool-patterns) — Arcade
- [Block's Goose - The Layered Tool Pattern](https://workos.com/blog/mcp-night-block-goose-layered-tool-pattern) — WorkOS
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) — Anthropic
- [MCP Server Best Practices for 2026](https://www.cdata.com/blog/mcp-server-best-practices-2026) — CData
