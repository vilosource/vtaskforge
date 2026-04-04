"""CLI commands for user management.

vtf user list/show
vtf member list/add/set-role/remove
vtf lock list/release
vtf channel-mapping list/create/delete
vtf service-account create
"""

import click
from vtf_sdk.exceptions import VtfError


# ---------------------------------------------------------------------------
# vtf user
# ---------------------------------------------------------------------------


@click.group()
def user():
    """Manage users (staff only)."""
    pass


@user.command("list")
@click.option("--type", "user_type", default=None, help="Filter by type (human, agent, service)")
@click.option("--search", default=None, help="Search by username")
@click.pass_context
def user_list(ctx, user_type, search):
    """List all users."""
    client = ctx.obj["client"]
    try:
        result = client.users.list(user_type=user_type, search=search)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No users found.")
        return
    click.echo(f"{'ID':<6} {'Username':<20} {'Type':<10} {'Staff':<7} {'Last Login'}")
    click.echo("-" * 65)
    for u in result.items:
        last_login = u.get("last_login") or "--"
        staff = "Yes" if u.get("is_staff") else "No"
        click.echo(f"{u['id']:<6} {u['username']:<20} {u.get('user_type', '--'):<10} {staff:<7} {last_login}")


@user.command("show")
@click.argument("id")
@click.pass_context
def user_show(ctx, id):
    """Show user details."""
    client = ctx.obj["client"]
    try:
        u = client.users.get(int(id))
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Username:  {u['username']}")
    click.echo(f"Type:      {u.get('user_type', '--')}")
    click.echo(f"Staff:     {'Yes' if u.get('is_staff') else 'No'}")
    click.echo(f"Active:    {'Yes' if u.get('is_active') else 'No'}")
    click.echo(f"Joined:    {u.get('date_joined', '--')}")
    click.echo(f"Last login: {u.get('last_login') or '--'}")
    memberships = u.get("memberships", [])
    if memberships:
        click.echo(f"\nProjects:")
        for m in memberships:
            proj = m.get("project", {})
            proj_display = proj.get("name", proj.get("id", "--")) if isinstance(proj, dict) else str(proj)
            click.echo(f"  {proj_display:<20} {m['role']}")


# ---------------------------------------------------------------------------
# vtf member
# ---------------------------------------------------------------------------


@click.group()
def member():
    """Manage project memberships (staff only)."""
    pass


@member.command("list")
@click.argument("project_id")
@click.pass_context
def member_list(ctx, project_id):
    """List members of a project."""
    client = ctx.obj["client"]
    try:
        result = client.members.list(project_id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No members found.")
        return
    click.echo(f"{'ID':<6} {'User':<20} {'Role':<10} {'Since'}")
    click.echo("-" * 55)
    for m in result.items:
        user_display = m.get("user", {})
        if isinstance(user_display, dict):
            user_display = user_display.get("username", str(user_display.get("id", "--")))
        click.echo(f"{m['id']:<6} {str(user_display):<20} {m['role']:<10} {m.get('created_at', '--')}")


@member.command("add")
@click.argument("project_id")
@click.argument("username")
@click.option("--role", default="member", type=click.Choice(["owner", "member", "viewer"]), help="Role")
@click.pass_context
def member_add(ctx, project_id, username, role):
    """Add a user to a project."""
    client = ctx.obj["client"]
    try:
        result = client.members.add(project_id, username=username, role=role)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    user_display = result.get("user", {})
    if isinstance(user_display, dict):
        user_display = user_display.get("username", username)
    click.echo(f"Added {user_display} as {result.get('role', role)} to {project_id}")


@member.command("set-role")
@click.argument("project_id")
@click.argument("membership_id")
@click.argument("role", type=click.Choice(["owner", "member", "viewer"]))
@click.pass_context
def member_set_role(ctx, project_id, membership_id, role):
    """Change a member's role."""
    client = ctx.obj["client"]
    try:
        result = client.members.set_role(project_id, int(membership_id), role=role)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Updated role to {result.get('role', role)}")


@member.command("remove")
@click.argument("project_id")
@click.argument("membership_id")
@click.pass_context
def member_remove(ctx, project_id, membership_id):
    """Remove a member from a project."""
    client = ctx.obj["client"]
    try:
        client.members.remove(project_id, int(membership_id))
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Removed membership {membership_id} from {project_id}")


# ---------------------------------------------------------------------------
# vtf lock
# ---------------------------------------------------------------------------


@click.group()
def lock():
    """Manage agent session locks."""
    pass


@lock.command("list")
@click.option("--project", "project_id", default=None, help="Filter by project ID")
@click.pass_context
def lock_list(ctx, project_id):
    """List active agent locks."""
    client = ctx.obj["client"]
    try:
        result = client.locks.list(project_id=project_id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No active locks.")
        return
    click.echo(f"{'ID':<6} {'Project':<20} {'Role':<15} {'Held by':<15} {'Since'}")
    click.echo("-" * 75)
    for lk in result.items:
        proj = lk.get("project", {})
        proj_display = proj.get("id", "--") if isinstance(proj, dict) else str(proj)
        user_display = lk.get("user", {})
        if isinstance(user_display, dict):
            user_display = user_display.get("username", str(user_display.get("id", "--")))
        click.echo(
            f"{lk['id']:<6} {str(proj_display):<20} {lk['role']:<15} "
            f"{str(user_display):<15} {lk.get('created_at', '--')}"
        )


@lock.command("release")
@click.argument("lock_id")
@click.pass_context
def lock_release(ctx, lock_id):
    """Release an agent lock."""
    client = ctx.obj["client"]
    try:
        client.locks.release(int(lock_id))
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Released lock {lock_id}")


# ---------------------------------------------------------------------------
# vtf channel-mapping
# ---------------------------------------------------------------------------


@click.group("channel-mapping")
def channel_mapping():
    """Manage channel-to-project mappings (staff only)."""
    pass


@channel_mapping.command("list")
@click.option("--provider", default=None, help="Filter by provider (slack, teams, etc.)")
@click.pass_context
def channel_mapping_list(ctx, provider):
    """List channel mappings."""
    client = ctx.obj["client"]
    try:
        result = client.channel_mappings.list(provider=provider)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No channel mappings.")
        return
    click.echo(f"{'ID':<6} {'Provider':<10} {'Channel':<20} {'Name':<15} {'Project'}")
    click.echo("-" * 65)
    for m in result.items:
        proj = m.get("project", {})
        proj_display = proj.get("id", "--") if isinstance(proj, dict) else str(proj)
        click.echo(
            f"{m['id']:<6} {m['provider']:<10} {m['channel_id']:<20} "
            f"{m.get('channel_name', ''):<15} {proj_display}"
        )


@channel_mapping.command("create")
@click.option("--provider", required=True, help="Provider (slack, teams, etc.)")
@click.option("--channel-id", required=True, help="Channel ID")
@click.option("--project", "project_id", required=True, help="Project ID")
@click.option("--channel-name", default="", help="Display name (optional)")
@click.pass_context
def channel_mapping_create(ctx, provider, channel_id, project_id, channel_name):
    """Create a channel mapping."""
    client = ctx.obj["client"]
    try:
        client.channel_mappings.create(
            provider=provider, channel_id=channel_id,
            project_id=project_id, channel_name=channel_name,
        )
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Created mapping: {provider}:{channel_id} -> {project_id}")


@channel_mapping.command("delete")
@click.argument("id")
@click.pass_context
def channel_mapping_delete(ctx, id):
    """Delete a channel mapping."""
    client = ctx.obj["client"]
    try:
        client.channel_mappings.delete(int(id))
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Deleted mapping {id}")


# ---------------------------------------------------------------------------
# vtf service-account
# ---------------------------------------------------------------------------


@click.group("service-account")
def service_account():
    """Manage service accounts (staff only)."""
    pass


@service_account.command("create")
@click.argument("name")
@click.pass_context
def service_account_create(ctx, name):
    """Create a service account and return its token."""
    client = ctx.obj["client"]
    try:
        result = client.service_accounts.create(name=name)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Created service account: {result['username']}")
    click.echo(f"Token: {result['token']}")
    click.echo("Save this token — it cannot be retrieved later.")
