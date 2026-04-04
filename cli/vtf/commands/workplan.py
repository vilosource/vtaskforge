import click
from vtf_sdk.exceptions import VtfError
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
    proj = project or cfg.project
    if not proj:
        click.echo("Error: project is required. Use --project or set default with 'vtf config set project <id>'", err=True)
        raise SystemExit(1)
    kwargs = {"description": description}
    if tags:
        kwargs["tags"] = [t.strip() for t in tags.split(",")]
    try:
        wp = client.workplans.create(name=name, project=proj, **kwargs)
        click.echo(f"Created workplan {wp.id}: {wp.name}")
    except VtfError as e:
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
    proj = project or cfg.project
    try:
        result = client.workplans.list(project_id=proj)
        if not result.items:
            click.echo("No workplans found.")
            return
        click.echo(f"{'ID':<36} {'Name':<30} {'Status':<12}")
        click.echo("-" * 80)
        for wp in result.items:
            click.echo(f"{wp.id:<36} {wp.name:<30} {wp.status:<12}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show workplan details."""
    client = ctx.obj["client"]
    try:
        wp = client.workplans.get(id)
        click.echo(f"ID:          {wp.id}")
        click.echo(f"Name:        {wp.name}")
        click.echo(f"Status:      {wp.status}")
        click.echo(f"Description: {wp.description}")
        click.echo(f"Tags:        {', '.join(wp.tags)}")
        click.echo(f"Created:     {wp.created_at}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def archive(ctx, id):
    """Archive a workplan."""
    client = ctx.obj["client"]
    try:
        client.workplans.archive(id)
        click.echo(f"Archived workplan {id}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def complete(ctx, id):
    """Complete a workplan."""
    client = ctx.obj["client"]
    try:
        client.workplans.complete(id)
        click.echo(f"Completed workplan {id}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@workplan.command()
@click.argument("id")
@click.pass_context
def stats(ctx, id):
    """Display workplan progress stats."""
    client = ctx.obj["client"]
    try:
        data = client.workplans.stats(id)
    except VtfError as e:
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
@click.option("--name", required=True, help="Milestone name")
@click.option("--workplan", required=True, help="Workplan ID")
@click.option("--description", default=None, help="Description")
@click.option("--sort-order", default=None, type=int, help="Sort order")
@click.pass_context
def create(ctx, name, workplan, description, sort_order):
    """Create a new milestone."""
    client = ctx.obj["client"]
    kwargs = {}
    if description is not None:
        kwargs["description"] = description
    if sort_order is not None:
        kwargs["order"] = sort_order
    try:
        ms = client.milestones.create(name=name, workplan=workplan, **kwargs)
        click.echo(f"Created milestone {ms.id}: {ms.name}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@milestone.command("list")
@click.option("--workplan", required=True, help="Workplan ID")
@click.pass_context
def list_milestones(ctx, workplan):
    """List milestones for a workplan."""
    client = ctx.obj["client"]
    try:
        result = client.milestones.list(workplan_id=workplan)
        if not result.items:
            click.echo("No milestones found.")
            return
        click.echo(f"{'ID':<36} {'Order':<6} {'Name':<30}")
        click.echo("-" * 74)
        for ms in result.items:
            click.echo(f"{ms.id:<36} {str(ms.order):<6} {ms.name:<30}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@milestone.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show milestone details."""
    client = ctx.obj["client"]
    try:
        ms = client.milestones.get(id)
        click.echo(f"ID:          {ms.id}")
        click.echo(f"Name:        {ms.name}")
        click.echo(f"Status:      {ms.status}")
        click.echo(f"Description: {ms.description}")
        click.echo(f"Order:       {ms.order}")
        click.echo(f"Workplan:    {ms.workplan}")
        click.echo(f"Created:     {ms.created_at}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@milestone.command()
@click.argument("id")
@click.option("--name", default=None, help="New name")
@click.option("--description", default=None, help="New description")
@click.option("--sort-order", default=None, type=int, help="New sort order")
@click.pass_context
def update(ctx, id, name, description, sort_order):
    """Update a milestone."""
    client = ctx.obj["client"]
    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if sort_order is not None:
        kwargs["order"] = sort_order
    if not kwargs:
        click.echo("No fields to update. Provide --name, --description, or --sort-order.", err=True)
        raise SystemExit(1)
    try:
        client.milestones.update(id, **kwargs)
        click.echo(f"Updated milestone {id}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@milestone.command()
@click.argument("id")
@click.pass_context
def stats(ctx, id):
    """Display milestone progress stats."""
    client = ctx.obj["client"]
    try:
        data = client.milestones.stats(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Total tasks: {data['total_tasks']}")
    click.echo(f"Completed: {data['completed_percentage']}%")
    for status, count in data.get("by_status", {}).items():
        click.echo(f"  {status}: {count}")
