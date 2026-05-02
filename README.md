# vtaskforge

A task execution platform for AI agents. Agents claim tasks from a board, execute them, and report results. The system manages the full lifecycle — from draft through review, execution, and completion — with structured specs so any agent can pick up any task cold.

## How it works

```
Project → Workplan → Milestones → Tasks → Agents claim and execute
```

- **Projects** contain workplans and link to a source repository
- **Workplans** group related work (e.g., "Auth system rewrite")
- **Milestones** are ordered stages within a workplan — tasks can only be worked when the milestone is active
- **Tasks** are self-contained agent work packets with full implementation specs
- **Agents** (executor and judge) claim tasks, execute them, and report results autonomously

Tasks carry everything an agent needs: description, acceptance criteria, implementation approach, file lists, constraints, references, and test commands.

## Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Server | Django 5.1 + DRF | REST API, task state machine, SSE events |
| Database | PostgreSQL 16 | Central store, atomic claims |
| Background | Celery + Redis | Claim expiry, periodic tasks |
| Web UI | React 18 + TypeScript | Kanban board, task detail, agent fleet view |
| MCP Server | FastMCP | Tool interface for Claude Code agents |
| CLI | Python (Click) | `vtf` command-line tool |

## Task lifecycle

```
draft → todo → doing → pending_completion_review → done
                 ↑                    ↓
                 └── changes_requested ←
```

- **Milestone enforcement**: tasks can only be submitted when their milestone is active
- **Review gate**: tasks with `needs_review_on_completion` go to `pending_completion_review` for judge verification
- **Rework flow**: judge rejects → `changes_requested` → any executor reclaims and fixes based on feedback

## Quick start

```bash
# Start all services
docker compose up -d
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser

# Verify
curl http://localhost:8000/v1/health
```

The API is at `http://localhost:8000`. Web UI at the same URL. MCP server at `http://localhost:8002`.

### Using with Claude Code (development & testing)

vtf includes an MCP server that Claude Code can connect to for interactive task execution. This is useful for developing task specs, testing workflows, and trying out vtf locally. Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "vtf": { "type": "http", "url": "http://localhost:8002/mcp" }
  }
}
```

Then in Claude Code: "Find the next task from vtf and implement it." Claude Code will claim a task, read the spec, implement the code, run tests, and submit the result.

See [docs/guides/local-quickstart-GUIDE.md](docs/guides/local-quickstart-GUIDE.md) for a full walkthrough covering project setup, task creation, and execution with Claude Code.

For **autonomous, unattended execution** (agents running as long-lived pods in Kubernetes), see [vafi](https://github.com/vilosource/vafi) — the agent fleet infrastructure that deploys executor and judge agents against a vtf instance.

## CLI (`vtf`)

```bash
# Install (development)
cd cli && pip install -e .

# Configure
vtf config set api_url http://localhost:8000

# Core workflow
vtf workplan list                          # List workplans
vtf import phases/phase1/ --workplan <id>  # Import phase with task specs
vtf task list --status todo                # Find claimable tasks
vtf task show <id>                         # View task details + spec
vtf task show <id> --json                  # Full JSON (for agents)
vtf task submit <id>                       # Move draft → todo
vtf task claim <id> --agent <agent-id>     # Claim a task
vtf task complete <id>                     # Mark done
vtf task fail <id>                         # Mark failed → needs_attention
```

## Web UI

The React SPA provides a Kanban board, full-page task detail view with parsed spec rendering, agent fleet overview, and execution trace links (via CXDB integration).

```bash
cd web && npm install && npm run dev    # Development (port 3000, proxies API)
```

## Deployment

vtf is deployed via **Argo CD** (GitOps). The Helm chart in `charts/vtf/` is rendered by Argo CD using values from the separate `vtf-deploy` repo (`environments/dev.yaml`, `environments/prod.yaml`).

To roll out a new vtf image, all 4 workloads (api, mcp, celery, celery-beat) move atomically:

```bash
# 1. Build + push (vtf-deploy/scripts/release.sh dev)
# 2. Edit vtf-deploy/environments/dev.yaml: image.tag=<git-sha>
# 3. Commit + push to vtf-deploy main — Argo CD syncs within ~3 min
#    (force immediate: argocd app sync vtf-dev)
```

Direct `helm upgrade` and `kubectl set image` will be reverted by Argo CD's selfHeal.

## Running tests

```bash
# Backend (1105+ tests)
pytest tests/                              # All tests
pytest tests/tasks/                        # Specific app

# Frontend (122+ tests)
cd web && npx vitest run                   # All frontend tests

# CLI
cd cli && pytest tests/                    # CLI tests
```

## Task specs

Tasks store their full implementation contract in the `spec` field — a YAML document:

```yaml
description: |
  What to build and why.

files:
  create: [new_file.py]
  modify: [existing_file.py]

implementation:
  approach: |
    Step-by-step instructions.
  constraints:
    - Hard rules the implementation must follow
  references:
    - files/to/read/first.py

acceptance_criteria:
  - "What success looks like"

test_command:
  unit: "pytest tests/specific_test.py"
```

## Integration with vafi

[vafi](https://github.com/vilosource/vafi) (Viloforge Agentic Fleet Infrastructure) deploys autonomous executor and judge agents that work against the vtf API. Agents pull tasks, execute them via Claude Code CLI, and report results. Execution traces are captured in CXDB and linked back to tasks via the `?expand=traces` API.

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/design/vtaskforge-DESIGN.md](docs/design/vtaskforge-DESIGN.md) | Core design: concepts, entity shapes, decisions |
| [docs/design/api-surface-DESIGN.md](docs/design/api-surface-DESIGN.md) | REST API endpoints, SSE events, error model |
| [docs/design/actor-model-DESIGN.md](docs/design/actor-model-DESIGN.md) | Agent roles, interaction patterns |
| [docs/e2e-testing-STRATEGY.md](docs/e2e-testing-STRATEGY.md) | E2E testing strategy: local and post-deploy |
| [docs/guides/quickstart-GUIDE.md](docs/guides/quickstart-GUIDE.md) | Zero to running in 5 minutes |
| [docs/guides/phase-process-GUIDE.md](docs/guides/phase-process-GUIDE.md) | How to plan and execute phases |
| [docs/guides/task-breakdown-GUIDE.md](docs/guides/task-breakdown-GUIDE.md) | Decomposing work into agent tasks |

## License

MIT
<!-- ci smoketest 2026-05-02T09:32:40Z -->
<!-- ci smoketest 2 2026-05-02T09:35:10Z -->
<!-- ci smoketest 3 2026-05-02T09:37:00Z -->
<!-- ci smoketest 4 2026-05-02T09:38:28Z -->
