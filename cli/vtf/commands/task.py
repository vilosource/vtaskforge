import json
import click
from vtf.client import VTFAPIError, unwrap_list
from vtf.config import Config


@click.group()
def task():
    """Manage tasks."""
    pass


@task.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--workplan", default=None, help="Filter by workplan ID")
@click.option("--milestone", default=None, help="Filter by milestone ID")
@click.option("--project", default=None, help="Filter by project ID")
@click.pass_context
def list_tasks(ctx, status, workplan, milestone, project):
    """List tasks."""
    client = ctx.obj["client"]
    cfg = Config()
    params = {}
    if status:
        params["status"] = status
    if workplan:
        params["workplan"] = workplan
    if milestone:
        params["milestone"] = milestone
    if project:
        params["project"] = project
    elif cfg.project:
        params["project"] = cfg.project
    try:
        results = unwrap_list(client.get("/v1/tasks/", params=params if params else None))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No tasks found.")
        return
    click.echo(f"{'ID':<25} {'Title':<35} {'Status':<15}")
    click.echo("-" * 75)
    for t in results:
        title = t['title'][:33] + '..' if len(t['title']) > 35 else t['title']
        click.echo(f"{t['id']:<25} {title:<35} {t['status']:<15}")


@task.command()
@click.argument("id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def show(ctx, id, as_json):
    """Show task details."""
    client = ctx.obj["client"]
    try:
        t = client.get(f"/v1/tasks/{id}/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if as_json:
        import json
        click.echo(json.dumps(t, indent=2))
        return

    click.echo(f"ID:          {t['id']}")
    click.echo(f"Title:       {t['title']}")
    click.echo(f"Status:      {t['status']}")
    click.echo(f"Milestone:   {t.get('milestone', '')}")
    click.echo(f"Workplan:    {t.get('workplan', '')}")
    click.echo(f"Claimed by:  {t.get('claimed_by', 'none')}")
    click.echo(f"Requires:    {', '.join(t.get('requires', []))}")
    if t.get('agent_model'):
        click.echo(f"Agent model: {t['agent_model']}")
    if t.get('isolation') and t['isolation'] != 'sequential':
        click.echo(f"Isolation:   {t['isolation']}")
    if t.get('judge'):
        click.echo(f"Judge:       Yes")
    if t.get('test_command'):
        cmds = t['test_command']
        if isinstance(cmds, dict):
            for k, v in cmds.items():
                click.echo(f"Test ({k}):  {v}")
    if t.get('description'):
        click.echo(f"\nDescription:\n{t['description']}")
    if t.get('spec'):
        click.echo(f"\nSpec: ({len(t['spec'])} chars, use --json for full content)")


@task.command()
@click.argument("id")
@click.pass_context
def submit(ctx, id):
    """Submit a draft task for execution."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/tasks/{id}/submit/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Submitted task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--tags", default="", help="Comma-separated agent tags")
@click.pass_context
def claim(ctx, id, agent, tags):
    """Claim a task for an agent."""
    client = ctx.obj["client"]
    data = {"agent_id": agent}
    if tags:
        data["tags"] = [t.strip() for t in tags.split(",")]
    try:
        result = client.post(f"/v1/tasks/{id}/claim/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Claimed task {id} by {agent} -> {result['status']}")


@task.command()
@click.argument("id")
@click.pass_context
def complete(ctx, id):
    """Mark a task as complete."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/tasks/{id}/complete/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Completed task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.pass_context
def fail(ctx, id):
    """Mark a task as failed (needs attention)."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/tasks/{id}/fail/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Failed task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.pass_context
def events(ctx, id):
    """Display event timeline for a task."""
    client = ctx.obj["client"]
    try:
        results = unwrap_list(client.get(f"/v1/tasks/{id}/events/"))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No events found.")
        return
    for event in results:
        click.echo(f"  {event['event_type']:20s} | {event.get('triggered_by', ''):15s} | {json.dumps(event.get('data', {}))}")


@task.command()
@click.option("--tags", default="", help="Comma-separated agent tags")
@click.option("--project", default=None, help="Filter by project ID")
@click.pass_context
def claimable(ctx, tags, project):
    """List tasks claimable by an agent with given tags."""
    client = ctx.obj["client"]
    cfg = Config()
    params = {}
    if tags:
        params["tags"] = tags
    if project:
        params["project"] = project
    elif cfg.project:
        params["project"] = cfg.project
    try:
        results = unwrap_list(client.get("/v1/tasks/claimable/", params=params if params else None))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No claimable tasks.")
        return
    click.echo(f"{'ID':<25} {'Title':<35} {'Requires':<15}")
    click.echo("-" * 75)
    for t in results:
        title = t['title'][:33] + '..' if len(t['title']) > 35 else t['title']
        requires = ', '.join(t.get('requires', []))
        click.echo(f"{t['id']:<25} {title:<35} {requires:<15}")


@task.command()
@click.argument("title")
@click.option("--project", help="Project ID")
@click.option("--workplan", help="Workplan ID")
@click.option("--milestone", help="Milestone ID")
@click.option("--labels", default="", help="Comma-separated labels")
@click.option("--description", default="", help="Task description")
@click.pass_context
def create(ctx, title, project, workplan, milestone, labels, description):
    """Create a new task."""
    client = ctx.obj["client"]
    cfg = Config()

    data = {"title": title, "description": description}

    # Set project (required)
    if project:
        data["project"] = project
    elif cfg.project:
        data["project"] = cfg.project
    else:
        click.echo("Error: project is required. Use --project or set default with 'vtf config set project <id>'", err=True)
        raise SystemExit(1)

    # Set optional workplan and milestone
    if workplan:
        data["workplan"] = workplan
    if milestone:
        data["milestone"] = milestone

    # Set labels
    if labels:
        data["labels"] = [l.strip() for l in labels.split(",")]

    try:
        result = client.post("/v1/tasks/", data)
        click.echo(f"Created task {result['id']}: {result['title']}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--decision", required=True, type=click.Choice(["approved", "changes_requested", "rejected"]), help="Review decision")
@click.option("--reason", default="", help="Review reason (required for changes_requested/rejected)")
@click.option("--reviewer", default="cli-user", help="Reviewer ID")
@click.option("--reviewer-type", "reviewer_type", default="human", type=click.Choice(["human", "agent"]), help="Reviewer type")
@click.pass_context
def review(ctx, id, decision, reason, reviewer, reviewer_type):
    """Submit a review for a task."""
    if decision in ("changes_requested", "rejected") and not reason:
        click.echo(f"Error: --reason is required when decision is '{decision}'", err=True)
        raise SystemExit(1)
    client = ctx.obj["client"]
    data = {
        "decision": decision,
        "reason": reason,
        "reviewer_id": reviewer,
        "reviewer_type": reviewer_type,
    }
    try:
        result = client.post(f"/v1/tasks/{id}/reviews/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Review submitted for task {id}: decision={result['decision']}")


@task.command()
@click.argument("id")
@click.option("--status", "target_status", required=True, help="Target status to force-transition to")
@click.option("--reason", required=True, help="Reason for force transition (audit trail)")
@click.pass_context
def reset(ctx, id, target_status, reason):
    """Force-transition a task to any status (admin)."""
    client = ctx.obj["client"]
    data = {"status": target_status, "reason": reason}
    try:
        result = client.post(f"/v1/tasks/{id}/reset/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Reset task {id}: {result.get('status', target_status)} (reason: {reason})")


@task.command()
@click.argument("id")
@click.option("--reason", default="", help="Optional comment for approval")
@click.pass_context
def approve(ctx, id, reason):
    """Approve a task (shortcut for review --decision approved)."""
    client = ctx.obj["client"]
    data = {
        "decision": "approved",
        "reason": reason,
        "reviewer_id": "cli-user",
        "reviewer_type": "human",
    }
    try:
        result = client.post(f"/v1/tasks/{id}/reviews/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Approved task {id}: decision={result['decision']}")


@task.command()
@click.argument("id")
@click.option("--reason", required=True, help="Reason for rejection (required)")
@click.pass_context
def reject(ctx, id, reason):
    """Reject a task (shortcut for review --decision changes_requested)."""
    client = ctx.obj["client"]
    data = {
        "decision": "changes_requested",
        "reason": reason,
        "reviewer_id": "cli-user",
        "reviewer_type": "human",
    }
    try:
        result = client.post(f"/v1/tasks/{id}/reviews/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Rejected task {id}: decision={result['decision']}")


@task.command()
@click.argument("id")
@click.option("--reason", default="", help="Reason for blocking")
@click.pass_context
def block(ctx, id, reason):
    """Block a task."""
    client = ctx.obj["client"]
    data = {"reason": reason} if reason else None
    try:
        result = client.post(f"/v1/tasks/{id}/block/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Blocked task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.pass_context
def unblock(ctx, id):
    """Unblock a task."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/tasks/{id}/unblock/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Unblocked task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.pass_context
def defer(ctx, id):
    """Defer a task."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/tasks/{id}/defer/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Deferred task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.pass_context
def cancel(ctx, id):
    """Cancel a task."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/tasks/{id}/cancel/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Cancelled task {id} -> {result['status']}")


@task.command()
@click.argument("id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(ctx, id, yes):
    """Delete a task."""
    if not yes:
        click.confirm(f"Delete task {id}?", abort=True)
    client = ctx.obj["client"]
    try:
        client.delete(f"/v1/tasks/{id}/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Deleted task {id}")


@task.command()
@click.argument("id")
@click.option("--title", default=None, help="Task title")
@click.option("--description", default=None, help="Task description")
@click.option("--labels", default=None, help="Comma-separated labels")
@click.option("--spec", default=None, help="Task spec text")
@click.option("--spec-file", default=None, type=click.Path(exists=True), help="Read spec from file")
@click.option("--agent-model", default=None, help="Agent model override")
@click.option("--judge/--no-judge", default=None, help="Enable/disable judge review")
@click.option("--isolation", default=None, help="Isolation mode")
@click.option("--workplan", default=None, help="Workplan ID")
@click.option("--milestone", default=None, help="Milestone ID")
@click.option("--acceptance-criteria", default=None, help="JSON array of criteria")
@click.option("--requires", default=None, help="Comma-separated task IDs")
@click.option("--test-command", default=None, help="JSON test command dict")
@click.option("--needs-review-before-start/--no-review-before-start", default=None, help="Require review before start")
@click.option("--needs-review-on-completion/--no-review-on-completion", default=None, help="Require review on completion")
@click.pass_context
def update(ctx, id, title, description, labels, spec, spec_file, agent_model, judge, isolation,
           workplan, milestone, acceptance_criteria, requires, test_command,
           needs_review_before_start, needs_review_on_completion):
    """Update task fields."""
    data = {}
    if title is not None:
        data["title"] = title
    if description is not None:
        data["description"] = description
    if labels is not None:
        data["labels"] = [l.strip() for l in labels.split(",")]
    if spec is not None:
        data["spec"] = spec
    if spec_file is not None:
        with open(spec_file) as f:
            data["spec"] = f.read()
    if agent_model is not None:
        data["agent_model"] = agent_model
    if judge is not None:
        data["judge"] = judge
    if isolation is not None:
        data["isolation"] = isolation
    if workplan is not None:
        data["workplan"] = workplan
    if milestone is not None:
        data["milestone"] = milestone
    if acceptance_criteria is not None:
        try:
            data["acceptance_criteria"] = json.loads(acceptance_criteria)
        except json.JSONDecodeError:
            click.echo("Error: --acceptance-criteria has invalid JSON", err=True)
            raise SystemExit(1)
    if requires is not None:
        data["requires"] = [t.strip() for t in requires.split(",")]
    if test_command is not None:
        try:
            data["test_command"] = json.loads(test_command)
        except json.JSONDecodeError:
            click.echo("Error: --test-command has invalid JSON", err=True)
            raise SystemExit(1)
    if needs_review_before_start is not None:
        data["needs_review_before_start"] = needs_review_before_start
    if needs_review_on_completion is not None:
        data["needs_review_on_completion"] = needs_review_on_completion

    if not data:
        click.echo("Error: no fields to update. Use --title, --description, --labels, etc.", err=True)
        raise SystemExit(1)

    client = ctx.obj["client"]
    try:
        client.patch(f"/v1/tasks/{id}/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Updated task {id}")
