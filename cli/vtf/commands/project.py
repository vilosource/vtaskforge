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


# --- vtf project var … (secret-variable declarations) ---

@click.group()
def var():
    """Manage a project's secret-variable declarations."""
    pass


def _resolve_var(client, project, name, role):
    """Resolve (name, role) → the variable, or None. The API is PK-addressed;
    operators address by name + role, so resolve via a list call."""
    result = client.project_variables.list(project, role=role)
    for v in result.items:
        if v.name == name and v.role == role:
            return v
    return None


@var.command("list")
@click.argument("project")
@click.option("--role", type=click.Choice(["executor", "judge"]), default=None,
              help="Filter by role")
@click.pass_context
def var_list(ctx, project, role):
    """List a project's variables."""
    client = ctx.obj["client"]
    try:
        result = client.project_variables.list(project, role=role)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No variables found.")
        return
    click.echo(f"{'ID':<24} {'NAME':<28} {'ROLE':<10} {'SCOPE':<9} {'REQ':<5}")
    click.echo("-" * 80)
    for v in result.items:
        click.echo(f"{v.id:<24} {v.name:<28} {v.role:<10} {v.scope:<9} {str(v.required):<5}")


@var.command("add")
@click.argument("project")
@click.argument("name")
@click.option("--role", type=click.Choice(["executor", "judge"]), required=True)
@click.option("--scope", type=click.Choice(["project", "shared"]), default="project")
@click.option("--description", default=None)
@click.option("--required/--not-required", default=True)
@click.option("--force", is_flag=True, help="Create even if a similar name exists")
@click.pass_context
def var_add(ctx, project, name, role, scope, description, required, force):
    """Add a variable declaration."""
    client = ctx.obj["client"]
    kwargs = {"scope": scope, "required": required}
    if description is not None:
        kwargs["description"] = description
    try:
        v = client.project_variables.create(project, name=name, role=role, force=force, **kwargs)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Added {v.role} variable {v.name} ({v.id})")


@var.command("show")
@click.argument("project")
@click.argument("name")
@click.option("--role", type=click.Choice(["executor", "judge"]), default="executor")
@click.pass_context
def var_show(ctx, project, name, role):
    """Show a variable by name + role."""
    client = ctx.obj["client"]
    try:
        v = _resolve_var(client, project, name, role)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if v is None:
        click.echo(f"Variable '{name}' ({role}) not found.", err=True)
        raise SystemExit(1)
    click.echo(f"ID:          {v.id}")
    click.echo(f"Name:        {v.name}")
    click.echo(f"Role:        {v.role}")
    click.echo(f"Scope:       {v.scope}")
    click.echo(f"Required:    {v.required}")
    click.echo(f"Description: {v.description or ''}")


@var.command("update")
@click.argument("project")
@click.argument("name")
@click.option("--role", type=click.Choice(["executor", "judge"]), default="executor")
@click.option("--description", default=None)
@click.option("--scope", type=click.Choice(["project", "shared"]), default=None)
@click.option("--required/--not-required", "required", default=None)
@click.pass_context
def var_update(ctx, project, name, role, description, scope, required):
    """Update a variable's description / scope / required."""
    client = ctx.obj["client"]
    try:
        v = _resolve_var(client, project, name, role)
        if v is None:
            click.echo(f"Variable '{name}' ({role}) not found.", err=True)
            raise SystemExit(1)
        kwargs = {}
        if description is not None:
            kwargs["description"] = description
        if scope is not None:
            kwargs["scope"] = scope
        if required is not None:
            kwargs["required"] = required
        updated = client.project_variables.update(project, v.id, **kwargs)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Updated {updated.name} (required={updated.required})")


@var.command("remove")
@click.argument("project")
@click.argument("name")
@click.option("--role", type=click.Choice(["executor", "judge"]), default="executor")
@click.pass_context
def var_remove(ctx, project, name, role):
    """Remove a variable by name + role."""
    client = ctx.obj["client"]
    try:
        v = _resolve_var(client, project, name, role)
        if v is None:
            click.echo(f"Variable '{name}' ({role}) not found.", err=True)
            raise SystemExit(1)
        client.project_variables.delete(project, v.id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Removed {role} variable {name}")


# Map a probe result to (symbol, human text). ✓ on resolvable, ✗ on failure.
_PROBE_RESULT_TEXT = {
    "success": ("✓", "vault: read OK, value present, {n} bytes"),
    "empty": ("✓", "vault: read OK, value present but empty"),
    "not_found": ("✗", "vault: 404 not found at expected path"),
    "permission_denied": ("✗", "vault: 403 permission denied"),
    "unreachable": ("✗", "vault: unreachable"),
    "not_probed": ("–", "not probed (judge SA — β)"),
}


@var.command("probe")
@click.argument("project")
@click.option("--probe-url", default=None,
              help="vafi controller probe base URL (overrides VTF_PROBE_URL / config probe_url)")
@click.pass_context
def var_probe(ctx, project, probe_url):
    """Pre-flight: resolve PROJECT's declared variables in Vault and report
    status (no values). Exits non-zero on required-variable failures."""
    import httpx
    from vtf.config import Config

    cfg = Config()
    base = probe_url or cfg.get_probe_url()
    if not base:
        click.echo("Error: probe URL not set — pass --probe-url, set VTF_PROBE_URL, "
                   "or `vtf config set probe_url <url>`.", err=True)
        raise SystemExit(2)
    try:
        resp = httpx.post(f"{base.rstrip('/')}/admin/probe", params={"project": project},
                          headers={"Authorization": f"Token {cfg.token or ''}"}, timeout=30.0)
    except httpx.HTTPError as e:
        click.echo(f"Error reaching probe endpoint: {e}", err=True)
        raise SystemExit(1)
    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", resp.text)
        except Exception:
            msg = resp.text
        click.echo(f"Error: HTTP {resp.status_code}: {msg}", err=True)
        raise SystemExit(1)

    rep = resp.json()
    click.echo(f"Project: {rep['project']}  (slug: {rep.get('slug', '?')})")
    click.echo(f"Environment: {rep.get('environment', '?')}\n")
    click.echo("Executor variables:")
    for v in rep.get("variables", []):
        symbol, text = _PROBE_RESULT_TEXT.get(v["result"], ("?", v["result"]))
        detail = text.format(n=v.get("size_bytes"))
        suffix = "  [optional]" if not v.get("required", True) else ""
        click.echo(f"  {symbol} {v['name']:<24} ({detail}){suffix}")
    result = rep.get("result", "FAIL")
    click.echo(f"\nResult: {result}")
    raise SystemExit(0 if result == "PASS" else 1)


project.add_command(var)
