"""CLI commands for user management.

vtf user list/show
vtf member list/add/set-role/remove
vtf lock list/release
vtf channel-mapping list/create/delete
vtf service-account create
"""

import click
from vtf.client import VTFClient, VTFAPIError, unwrap_list


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
    params = {}
    if user_type:
        params["user_type"] = user_type
    if search:
        params["search"] = search
    try:
        results = unwrap_list(client.get("/v1/users/", params=params or None))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No users found.")
        return
    click.echo(f"{'ID':<6} {'Username':<20} {'Type':<10} {'Staff':<7} {'Last Login'}")
    click.echo("-" * 65)
    for u in results:
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
        u = client.get(f"/v1/users/{id}/")
    except VTFAPIError as e:
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
            click.echo(f"  {m.get('project_id', '--'):<20} {m['role']}")


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
        results = unwrap_list(client.get(f"/v1/projects/{project_id}/members/"))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No members found.")
        return
    click.echo(f"{'ID':<6} {'Username':<20} {'Role':<10} {'Since'}")
    click.echo("-" * 55)
    for m in results:
        click.echo(f"{m['id']:<6} {m['username']:<20} {m['role']:<10} {m.get('created_at', '--')}")


@member.command("add")
@click.argument("project_id")
@click.argument("username")
@click.option("--role", default="member", type=click.Choice(["owner", "member", "viewer"]), help="Role")
@click.pass_context
def member_add(ctx, project_id, username, role):
    """Add a user to a project."""
    client = ctx.obj["client"]
    try:
        result = client.post(f"/v1/projects/{project_id}/members/", {"username": username, "role": role})
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Added {result['username']} as {result['role']} to {project_id}")


@member.command("set-role")
@click.argument("project_id")
@click.argument("membership_id")
@click.argument("role", type=click.Choice(["owner", "member", "viewer"]))
@click.pass_context
def member_set_role(ctx, project_id, membership_id, role):
    """Change a member's role."""
    client = ctx.obj["client"]
    try:
        result = client.patch(f"/v1/projects/{project_id}/members/{membership_id}/", {"role": role})
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Updated {result['username']} to {result['role']}")


@member.command("remove")
@click.argument("project_id")
@click.argument("membership_id")
@click.pass_context
def member_remove(ctx, project_id, membership_id):
    """Remove a member from a project."""
    client = ctx.obj["client"]
    try:
        client.delete(f"/v1/projects/{project_id}/members/{membership_id}/")
    except VTFAPIError as e:
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
    params = {"project_id": project_id} if project_id else None
    try:
        results = unwrap_list(client.get("/v1/locks/", params=params))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No active locks.")
        return
    click.echo(f"{'ID':<6} {'Project':<20} {'Role':<15} {'Held by':<15} {'Since'}")
    click.echo("-" * 75)
    for lk in results:
        click.echo(
            f"{lk['id']:<6} {lk['project_id']:<20} {lk['role']:<15} "
            f"{lk['user']:<15} {lk.get('created_at', '--')}"
        )


@lock.command("release")
@click.argument("lock_id")
@click.pass_context
def lock_release(ctx, lock_id):
    """Release an agent lock."""
    client = ctx.obj["client"]
    try:
        client.delete(f"/v1/locks/{lock_id}/")
    except VTFAPIError as e:
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
    params = {"provider": provider} if provider else None
    try:
        results = unwrap_list(client.get("/v1/channel-mappings/", params=params))
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not results:
        click.echo("No channel mappings.")
        return
    click.echo(f"{'ID':<6} {'Provider':<10} {'Channel':<20} {'Name':<15} {'Project'}")
    click.echo("-" * 65)
    for m in results:
        click.echo(
            f"{m['id']:<6} {m['provider']:<10} {m['channel_id']:<20} "
            f"{m.get('channel_name', ''):<15} {m['project_id']}"
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
    data = {"provider": provider, "channel_id": channel_id, "project_id": project_id}
    if channel_name:
        data["channel_name"] = channel_name
    try:
        result = client.post("/v1/channel-mappings/", data)
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Created mapping: {provider}:{channel_id} -> {result['project_id']}")


@channel_mapping.command("delete")
@click.argument("id")
@click.pass_context
def channel_mapping_delete(ctx, id):
    """Delete a channel mapping."""
    client = ctx.obj["client"]
    try:
        client.delete(f"/v1/channel-mappings/{id}/")
    except VTFAPIError as e:
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
        result = client.post("/v1/service-accounts/", {"name": name})
    except VTFAPIError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Created service account: {result['username']}")
    click.echo(f"Token: {result['token']}")
    click.echo("Save this token — it cannot be retrieved later.")
