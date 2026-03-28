# Local Quickstart — vtf + Claude Code

Run vtaskforge locally and use Claude Code to execute tasks against your own codebase.

## Prerequisites

- Docker and docker compose
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed
- A git repository you want to work on

## 1. Start vtf

```bash
git clone https://github.com/vilosource/vtaskforge.git
cd vtaskforge
docker compose up -d
docker compose exec api python src/manage.py migrate
docker compose exec api python src/manage.py createsuperuser
```

Verify:
```bash
curl http://localhost:8000/v1/health
# {"status":"healthy","checks":{"db":"ok","redis":"ok"}}
```

The API is at `http://localhost:8000`. Web UI at `http://localhost:8000`. MCP server at `http://localhost:8002`.

## 2. Get an API token

```bash
# Using the superuser you created
curl -X POST http://localhost:8000/api-token-auth/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<your-password>"}'
# {"token":"abc123..."}
```

Or create one via the Django shell:
```bash
docker compose exec api python src/manage.py shell -c "
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
u = User.objects.first()
t, _ = Token.objects.get_or_create(user=u)
print(t.key)
"
```

Export it for the CLI:
```bash
vtf config set api_url http://localhost:8000
vtf config set token <your-token>
```

## 3. Create a project

```bash
curl -X POST http://localhost:8000/v1/projects/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-project",
    "description": "My project",
    "repo_url": "git@github.com:youruser/yourrepo.git",
    "default_branch": "main"
  }'
# Note the project ID from the response
```

## 4. Create a workplan and milestone

```bash
# Create workplan
curl -X POST http://localhost:8000/v1/workplans/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Sprint 1", "project": "<project-id>"}'
# Note the workplan ID

# Create milestone
curl -X POST http://localhost:8000/v1/workplans/<workplan-id>/milestones/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Feature work"}'
# Note the milestone ID

# Activate the milestone (tasks can only be worked in active milestones)
curl -X POST http://localhost:8000/v1/milestones/<milestone-id>/activate/ \
  -H "Authorization: Token <your-token>"
```

## 5. Create a task

```bash
curl -X POST http://localhost:8000/v1/tasks/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add a greeting function",
    "description": "Add a greet(name) function that returns Hello, {name}!",
    "project": "<project-id>",
    "workplan": "<workplan-id>",
    "milestone": "<milestone-id>",
    "spec": "id: task-1\nname: Add a greeting function\ndescription: |\n  Add greet(name) that returns \"Hello, {name}!\"\nfiles:\n  create:\n    - src/greet.py\n    - tests/test_greet.py\nimplementation:\n  approach: |\n    1. Create src/greet.py with greet(name) function\n    2. Create tests/test_greet.py with tests\nacceptance_criteria:\n  - greet(\"World\") returns \"Hello, World!\"\n  - greet(\"\") returns \"Hello, !\"\ntest_command:\n  unit: python -m pytest tests/test_greet.py -v",
    "test_command": {"unit": "python -m pytest tests/test_greet.py -v"}
  }'
# Note the task ID
```

Submit the task to make it claimable:
```bash
curl -X POST http://localhost:8000/v1/tasks/<task-id>/submit/ \
  -H "Authorization: Token <your-token>"
```

## 6. Connect Claude Code to vtf

Add the vtf MCP server to your Claude Code configuration. Create or edit `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "vtf": {
      "type": "http",
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

Restart Claude Code to pick up the MCP server.

## 7. Execute the task with Claude Code

Open Claude Code in your project directory:

```bash
cd /path/to/your/repo
claude
```

Then tell Claude Code to work on the task:

```
> Find the next available task from vtf and implement it
```

Claude Code will use the vtf MCP tools to:
1. Find the claimable task (`vtf_next_work`)
2. Claim it (`vtf_claim_and_start`)
3. Read the spec and implement the code
4. Run tests
5. Submit the work (`vtf_submit_work`)

## 8. View results

Open the web UI at `http://localhost:8000` to see:
- The Kanban board with your task's status
- The task detail page with the implementation spec
- Notes from the agent with the completion report

## Using the CLI instead

You can also manage tasks via the `vtf` CLI:

```bash
# Install
cd vtaskforge/cli && pip install -e .

# Configure
vtf config set api_url http://localhost:8000
vtf config set token <your-token>

# Workflow
vtf workplan list
vtf task list --status todo
vtf task show <task-id>
vtf task show <task-id> --json    # Full spec for agents
```

## Next steps

- **Bulk import**: Create task specs as YAML files and import them with `vtf import`
- **Review workflow**: Set `needs_review_on_completion: true` on tasks to add a review gate
- **Multiple tasks**: Create a milestone with several tasks and dependencies — agents work through them in DAG order
- **Autonomous execution**: Use [vafi](https://github.com/vilosource/vafi) to run agents autonomously in containers
