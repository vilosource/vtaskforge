import click
from vtf_sdk.exceptions import VtfError


@click.group()
def project():
    """Manage projects."""
    pass


@project.command("list")
@click.pass_context
def list_projects(ctx):
    """List projects."""
    client = ctx.obj["client"]
    try:
        result = client.projects.list()
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No projects found.")
        return
    click.echo(f"{'ID':<25} {'Name':<35} {'Status':<15}")
    click.echo("-" * 75)
    for p in result.items:
        name = p.name[:33] + '..' if len(p.name) > 35 else p.name
        click.echo(f"{p.id:<25} {name:<35} {p.status:<15}")


@project.command()
@click.option("--name", required=True, help="Project name")
@click.option("--repo", help="Repository URL")
@click.option("--tags", default="", help="Comma-separated tags")
@click.pass_context
def create(ctx, name, repo, tags):
    """Create a new project."""
    client = ctx.obj["client"]
    kwargs = {}
    if repo:
        kwargs["repo_url"] = repo
    if tags:
        kwargs["tags"] = [t.strip() for t in tags.split(",")]
    try:
        p = client.projects.create(name=name, **kwargs)
        click.echo(f"Created project {p.id}: {p.name}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@project.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show project details."""
    client = ctx.obj["client"]
    try:
        p = client.projects.get(id)
        click.echo(f"ID:          {p.id}")
        click.echo(f"Name:        {p.name}")
        click.echo(f"Status:      {p.status}")
        click.echo(f"Description: {p.description}")
        click.echo(f"Repo URL:    {p.repo_url}")
        click.echo(f"Branch:      {p.default_branch or 'main'}")
        click.echo(f"Tags:        {', '.join(p.tags)}")
        click.echo(f"Created:     {p.created_at}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
