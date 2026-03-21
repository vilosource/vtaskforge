import click
from vtf.client import VTFAPIError
from vtf.config import Config


@click.group()
def workplan():
    """Manage workplans."""
    pass


@workplan.command()
@click.option("--name", required=True, help="Workplan name")
@click.option("--description", default="", help="Description")
@click.option("--tags", default="", help="Comma-separated tags")
@click.option("--project", help="Project ID")
@click.pass_context
def create(ctx, name, description, tags, project):
    """Create a new workplan."""
    client = ctx.obj["client"]
    cfg = Config()

    data = {"name": name, "description": description}

    # Set project (required)
    if project:
        data["project"] = project
    elif cfg.project:
        data["project"] = cfg.project
    else:
        click.echo("Error: project is required. Use --project or set default with 'vtf config set project <id>'", err=True)
        raise SystemExit(1)

    if tags:
        data["tags"] = [t.strip() for t in tags.split(",")]
    try:
        result = client.post("/v1/workplans/", data)
        click.echo(f"Created workplan {result['id']}: {result['name']}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--project", default=None, help="Filter by project ID")
@click.pass_context
def list_workplans(ctx, status, project):
    """List workplans."""
    client = ctx.obj["client"]
    cfg = Config()
    params = {}
    if status:
        params["status"] = status
    if project:
        params["project"] = project
    elif cfg.project:
        params["project"] = cfg.project
    try:
        from vtf.client import unwrap_list
        results = unwrap_list(client.get("/v1/workplans/", params=params if params else None))
        if not results:
            click.echo("No workplans found.")
            return
        click.echo(f"{'ID':<36} {'Name':<30} {'Status':<12}")
        click.echo("-" * 80)
        for wp in results:
            click.echo(f"{wp['id']:<36} {wp['name']:<30} {wp['status']:<12}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show workplan details."""
    client = ctx.obj["client"]
    try:
        wp = client.get(f"/v1/workplans/{id}/")
        click.echo(f"ID:          {wp['id']}")
        click.echo(f"Name:        {wp['name']}")
        click.echo(f"Status:      {wp['status']}")
        click.echo(f"Description: {wp.get('description', '')}")
        click.echo(f"Tags:        {', '.join(wp.get('tags', []))}")
        click.echo(f"Created:     {wp['created_at']}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def archive(ctx, id):
    """Archive a workplan."""
    client = ctx.obj["client"]
    try:
        client.post(f"/v1/workplans/{id}/archive/")
        click.echo(f"Archived workplan {id}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def complete(ctx, id):
    """Complete a workplan."""
    client = ctx.obj["client"]
    try:
        client.post(f"/v1/workplans/{id}/complete/")
        click.echo(f"Completed workplan {id}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def stats(ctx, id):
    """Display workplan progress stats."""
    client = ctx.obj["client"]
    try:
        data = client.get(f"/v1/workplans/{id}/stats/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Total tasks: {data['total_tasks']}")
    click.echo(f"Completed: {data['completed_percentage']}%")
    for status, count in data.get("by_status", {}).items():
        click.echo(f"  {status}: {count}")


@click.group()
def milestone():
    """Manage milestones."""
    pass


@milestone.command()
@click.argument("id")
@click.pass_context
def stats(ctx, id):
    """Display milestone progress stats."""
    client = ctx.obj["client"]
    try:
        data = client.get(f"/v1/milestones/{id}/stats/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Total tasks: {data['total_tasks']}")
    click.echo(f"Completed: {data['completed_percentage']}%")
    for status, count in data.get("by_status", {}).items():
        click.echo(f"  {status}: {count}")
