import click
from vtf.client import VTFClient, VTFAPIError
from vtf.config import Config
from vtf.commands.workplan import workplan
from vtf.commands.task import task
from vtf.commands.agent import agent


def get_client():
    cfg = Config()
    return VTFClient(cfg.api_url, cfg.token)


@click.group()
@click.pass_context
def cli(ctx):
    """vtf — vtaskforge CLI"""
    ctx.ensure_object(dict)
    ctx.obj["client"] = get_client()


@cli.command()
@click.pass_context
def health(ctx):
    """Check API connectivity."""
    client = ctx.obj["client"]
    try:
        data = client.health()
        click.echo(f"API is healthy: {data}")
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Connection failed: {e}", err=True)
        raise SystemExit(1)


@cli.group()
def config():
    """Manage CLI configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value (api_url, token)."""
    cfg = Config()
    cfg.set(key, value)
    click.echo(f"Set {key}")


@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = Config()
    click.echo(f"api_url: {cfg.api_url}")
    click.echo(f"token: {'***' if cfg.token else 'not set'}")


cli.add_command(workplan)
cli.add_command(task)
