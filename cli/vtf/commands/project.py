import click
from vtf.client import VTFAPIError, unwrap_list


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
        results = unwrap_list(client.get("/v1/projects/"))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No projects found.")
        return
    click.echo(f"{'ID':<25} {'Name':<35} {'Status':<15}")
    click.echo("-" * 75)
    for p in results:
        name = p['name'][:33] + '..' if len(p['name']) > 35 else p['name']
        click.echo(f"{p['id']:<25} {name:<35} {p['status']:<15}")


@project.command()
@click.option("--name", required=True, help="Project name")
@click.option("--repo", help="Repository URL")
@click.option("--tags", default="", help="Comma-separated tags")
@click.pass_context
def create(ctx, name, repo, tags):
    """Create a new project."""
    client = ctx.obj["client"]
    data = {"name": name}
    if repo:
        data["repo_url"] = repo
    if tags:
        data["tags"] = [t.strip() for t in tags.split(",")]
    try:
        result = client.post("/v1/projects/", data)
        click.echo(f"Created project {result['id']}: {result['name']}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@project.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show project details."""
    client = ctx.obj["client"]
    try:
        p = client.get(f"/v1/projects/{id}/")
        click.echo(f"ID:          {p['id']}")
        click.echo(f"Name:        {p['name']}")
        click.echo(f"Status:      {p['status']}")
        click.echo(f"Description: {p.get('description', '')}")
        click.echo(f"Repo URL:    {p.get('repo_url', '')}")
        click.echo(f"Branch:      {p.get('default_branch', 'main')}")
        click.echo(f"Tags:        {', '.join(p.get('tags', []))}")
        click.echo(f"Created:     {p['created_at']}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)