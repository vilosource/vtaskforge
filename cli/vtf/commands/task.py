import json
import click
from vtf.client import VTFAPIError, unwrap_list


@click.group()
def task():
    """Manage tasks."""
    pass


@task.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--workplan", default=None, help="Filter by workplan ID")
@click.option("--phase", default=None, help="Filter by phase ID")
@click.pass_context
def list_tasks(ctx, status, workplan, phase):
    """List tasks."""
    client = ctx.obj["client"]
    params = {}
    if status:
        params["status"] = status
    if workplan:
        params["workplan"] = workplan
    if phase:
        params["phase"] = phase
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
@click.pass_context
def show(ctx, id):
    """Show task details."""
    client = ctx.obj["client"]
    try:
        t = client.get(f"/v1/tasks/{id}/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"ID:          {t['id']}")
    click.echo(f"Title:       {t['title']}")
    click.echo(f"Status:      {t['status']}")
    click.echo(f"Phase:       {t.get('phase', '')}")
    click.echo(f"Workplan:    {t.get('workplan', '')}")
    click.echo(f"Claimed by:  {t.get('claimed_by', 'none')}")
    click.echo(f"Requires:    {', '.join(t.get('requires', []))}")
    if t.get('description'):
        click.echo(f"\nDescription:\n{t['description']}")


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
@click.pass_context
def claimable(ctx, tags):
    """List tasks claimable by an agent with given tags."""
    client = ctx.obj["client"]
    params = {"tags": tags} if tags else None
    try:
        results = unwrap_list(client.get("/v1/tasks/claimable/", params=params))
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
