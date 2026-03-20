import click
from vtf.client import VTFClient, VTFAPIError
from vtf.config import Config


@click.group()
def agent():
    """Manage agents."""
    pass


@agent.command()
@click.option("--name", required=True, help="Agent name")
@click.option("--tags", default="", help="Comma-separated tags")
def register(name, tags):
    """Register a new agent and save token to config."""
    cfg = Config()
    # Registration is unauthenticated — create client without token
    client = VTFClient(cfg.api_url, token=None)
    data = {"name": name}
    if tags:
        data["tags"] = [t.strip() for t in tags.split(",")]
    try:
        result = client.post("/v1/agents/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    token = result.get("token")
    if token:
        cfg.set("token", token)
        click.echo(f"Registered agent {result['id']}: {result['name']}")
        click.echo("Token saved to config.")
    else:
        click.echo(f"Registered agent {result['id']} (no token in response)")


@agent.command("list")
@click.option("--status", default=None, help="Filter by status (online, busy, offline)")
@click.pass_context
def list_agents(ctx, status):
    """List registered agents."""
    client = ctx.obj["client"]
    params = {"status": status} if status else None
    try:
        results = client.get("/v1/agents/", params=params)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No agents found.")
        return
    click.echo(f"{'ID':<36} {'Name':<25} {'Status':<10} {'Tags'}")
    click.echo("-" * 85)
    for a in results:
        tags = ", ".join(a.get("tags", []))
        click.echo(f"{a['id']:<36} {a['name']:<25} {a['status']:<10} {tags}")


@agent.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show agent details."""
    client = ctx.obj["client"]
    try:
        a = client.get(f"/v1/agents/{id}/")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"ID:             {a['id']}")
    click.echo(f"Name:           {a['name']}")
    click.echo(f"Status:         {a['status']}")
    click.echo(f"Tags:           {', '.join(a.get('tags', []))}")
    click.echo(f"Registered:     {a['registered_at']}")
    click.echo(f"Last heartbeat: {a.get('last_heartbeat', 'never')}")


@agent.command()
@click.argument("id")
@click.option(
    "--set",
    "new_status",
    required=True,
    type=click.Choice(["online", "busy", "offline"]),
    help="New status",
)
@click.pass_context
def status(ctx, id, new_status):
    """Update agent status."""
    client = ctx.obj["client"]
    try:
        result = client.patch(f"/v1/agents/{id}/", {"status": new_status})
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Agent {id} status set to {result['status']}")
