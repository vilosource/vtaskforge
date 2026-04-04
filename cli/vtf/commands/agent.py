import click
from vtf_sdk.client import VtfClient
from vtf_sdk.exceptions import VtfError
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
    client = VtfClient(url=cfg.api_url, token="")
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    try:
        a, raw = client.agents.register(name=name, tags=tag_list)
        token = raw.get("token")
        if token:
            cfg.set("token", token)
            click.echo(f"Registered agent {a.id}: {a.name}")
            click.echo("Token saved to config.")
        else:
            click.echo(f"Registered agent {a.id}: {a.name}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    finally:
        client.close()


@agent.command("list")
@click.option("--status", default=None, help="Filter by status (online, busy, offline)")
@click.pass_context
def list_agents(ctx, status):
    """List registered agents."""
    client = ctx.obj["client"]
    try:
        result = client.agents.list()
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No agents found.")
        return
    click.echo(f"{'ID':<36} {'Name':<25} {'Status':<10} {'Tags'}")
    click.echo("-" * 85)
    for a in result.items:
        tags = ", ".join(a.tags)
        click.echo(f"{a.id:<36} {a.name:<25} {a.status:<10} {tags}")


@agent.command()
@click.argument("id")
@click.pass_context
def show(ctx, id):
    """Show agent details."""
    client = ctx.obj["client"]
    try:
        a = client.agents.get(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"ID:             {a.id}")
    click.echo(f"Name:           {a.name}")
    click.echo(f"Status:         {a.status}")
    click.echo(f"Tags:           {', '.join(a.tags)}")
    click.echo(f"Registered:     {a.registered_at}")
    click.echo(f"Last heartbeat: {a.last_heartbeat or 'never'}")


@agent.command()
@click.argument("id")
@click.option("--set", "new_status", required=True,
              type=click.Choice(["online", "busy", "offline"]), help="New status")
@click.pass_context
def status(ctx, id, new_status):
    """Update agent status."""
    client = ctx.obj["client"]
    try:
        a = client.agents.update_status(id, status=new_status)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Agent {id} status set to {a.status}")
