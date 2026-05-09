import json
import click
from vtf_sdk.exceptions import VtfError
from vtf.config import Config


@click.group()
def task():
    """Manage tasks."""
    pass


@task.command("list")
@click.option("--status", default=None, help="Filter by status")
@click.option("--workplan", default=None, help="Filter by workplan ID")
@click.option("--milestone", default=None, help="Filter by milestone ID")
@click.option("--project", default=None, help="Filter by project ID")
@click.pass_context
def list_tasks(ctx, status, workplan, milestone, project):
    """List tasks."""
    client = ctx.obj["client"]
    cfg = Config()
    kwargs = {}
    if status:
        kwargs["status"] = status
    if workplan:
        kwargs["workplan_id"] = workplan
    if milestone:
        kwargs["milestone_id"] = milestone
    if project:
        kwargs["project_id"] = project
    elif cfg.project:
        kwargs["project_id"] = cfg.project
    try:
        result = client.tasks.list(**kwargs)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No tasks found.")
        return
    click.echo(f"{'ID':<25} {'Title':<35} {'Status':<15}")
    click.echo("-" * 75)
    for t in result.items:
        title = t.title[:33] + '..' if len(t.title) > 35 else t.title
        click.echo(f"{t.id:<25} {title:<35} {t.status:<15}")


@task.command()
@click.argument("id")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def show(ctx, id, as_json):
    """Show task details."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.get(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    if as_json:
        click.echo(json.dumps(t.model_dump(mode="json"), indent=2, default=str))
        return

    click.echo(f"ID:          {t.id}")
    click.echo(f"Title:       {t.title}")
    click.echo(f"Status:      {t.status}")
    click.echo(f"Milestone:   {t.milestone or ''}")
    click.echo(f"Workplan:    {t.workplan or ''}")
    click.echo(f"Claimed by:  {t.claimed_by or 'none'}")
    requires = ', '.join(str(r) for r in t.requires) if t.requires else ''
    click.echo(f"Requires:    {requires}")
    if t.required_tags:
        click.echo(f"Req. tags:   {', '.join(t.required_tags)}")
    if t.agent_model:
        click.echo(f"Agent model: {t.agent_model}")
    if t.isolation and t.isolation != 'sequential':
        click.echo(f"Isolation:   {t.isolation}")
    if t.judge:
        click.echo(f"Judge:       Yes")
    if t.test_command:
        cmds = t.test_command
        if isinstance(cmds, dict):
            for k, v in cmds.items():
                click.echo(f"Test ({k}):  {v}")
    if t.description:
        click.echo(f"\nDescription:\n{t.description}")
    if t.spec:
        click.echo(f"\nSpec: ({len(t.spec)} chars, use --json for full content)")


@task.command()
@click.argument("id")
@click.pass_context
def submit(ctx, id):
    """Submit a draft task for execution."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.submit(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Submitted task {id} -> {t.status}")


@task.command()
@click.argument("id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--tags", default="", help="Comma-separated agent tags")
@click.pass_context
def claim(ctx, id, agent, tags):
    """Claim a task for an agent."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.claim(id, agent_id=agent)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Claimed task {id} by {agent} -> {t.status}")


@task.command()
@click.argument("id")
@click.pass_context
def complete(ctx, id):
    """Mark a task as complete."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.complete(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Completed task {id} -> {t.status}")


@task.command()
@click.argument("id")
@click.pass_context
def fail(ctx, id):
    """Mark a task as failed (needs attention)."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.fail(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Failed task {id} -> {t.status}")


@task.command()
@click.argument("id")
@click.pass_context
def events(ctx, id):
    """Display event timeline for a task."""
    client = ctx.obj["client"]
    try:
        result = client.tasks.list_events(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No events found.")
        return
    for event in result.items:
        actor = str(event.actor) if event.actor else event.trigger_source
        click.echo(f"  {event.event_type:20s} | {actor:15s} | {json.dumps(event.data)}")


@task.command()
@click.option("--tags", default="", help="Comma-separated agent tags")
@click.option("--project", default=None, help="Filter by project ID")
@click.pass_context
def claimable(ctx, tags, project):
    """List tasks claimable by an agent with given tags."""
    client = ctx.obj["client"]
    cfg = Config()
    kwargs = {}
    if tags:
        kwargs["tags"] = [t.strip() for t in tags.split(",")]
    if project:
        kwargs["project_id"] = project
    elif cfg.project:
        kwargs["project_id"] = cfg.project
    try:
        result = client.tasks.claimable(**kwargs)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    if not result.items:
        click.echo("No claimable tasks.")
        return
    click.echo(f"{'ID':<25} {'Title':<35} {'Requires':<15}")
    click.echo("-" * 75)
    for t in result.items:
        title = t.title[:33] + '..' if len(t.title) > 35 else t.title
        requires = ', '.join(str(r) for r in t.requires) if t.requires else ''
        click.echo(f"{t.id:<25} {title:<35} {requires:<15}")


@task.command()
@click.argument("title")
@click.option("--project", help="Project ID")
@click.option("--workplan", help="Workplan ID")
@click.option("--milestone", help="Milestone ID")
@click.option("--labels", default="", help="Comma-separated labels")
@click.option("--description", default="", help="Task description")
@click.option("--required-tags", "required_tags", default=None,
              help="Comma-separated capability tags (e.g. 'executor,pi') the claiming agent must have")
@click.pass_context
def create(ctx, title, project, workplan, milestone, labels, description, required_tags):
    """Create a new task."""
    client = ctx.obj["client"]
    cfg = Config()

    proj = project or cfg.project
    if not proj:
        click.echo("Error: project is required. Use --project or set default with 'vtf config set project <id>'", err=True)
        raise SystemExit(1)

    kwargs = {"description": description}
    if workplan:
        kwargs["workplan"] = workplan
    if milestone:
        kwargs["milestone"] = milestone
    if labels:
        kwargs["labels"] = [l.strip() for l in labels.split(",")]
    if required_tags is not None:
        kwargs["required_tags"] = [t.strip() for t in required_tags.split(",") if t.strip()]

    try:
        t = client.tasks.create(title=title, project=proj, **kwargs)
        click.echo(f"Created task {t.id}: {t.title}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--decision", required=True, type=click.Choice(["approved", "changes_requested", "rejected"]), help="Review decision")
@click.option("--reason", default="", help="Review reason (required for changes_requested/rejected)")
@click.option("--reviewer", default="cli-user", help="Reviewer ID")
@click.option("--reviewer-type", "reviewer_type", default="human", type=click.Choice(["human", "agent"]), help="Reviewer type")
@click.pass_context
def review(ctx, id, decision, reason, reviewer, reviewer_type):
    """Submit a review for a task."""
    if decision in ("changes_requested", "rejected") and not reason:
        click.echo(f"Error: --reason is required when decision is '{decision}'", err=True)
        raise SystemExit(1)
    client = ctx.obj["client"]
    try:
        r = client.tasks.submit_review(id, decision=decision, reason=reason, reviewer_type=reviewer_type)
        click.echo(f"Review submitted for task {id}: decision={r.decision}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--status", "target_status", required=True, help="Target status to force-transition to")
@click.option("--reason", required=True, help="Reason for force transition (audit trail)")
@click.pass_context
def reset(ctx, id, target_status, reason):
    """Force-transition a task to any status (admin)."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.reset(id, status=target_status, reason=reason)
        click.echo(f"Reset task {id}: {t.status} (reason: {reason})")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--reason", default="", help="Optional comment for approval")
@click.pass_context
def approve(ctx, id, reason):
    """Approve a task (shortcut for review --decision approved)."""
    client = ctx.obj["client"]
    try:
        r = client.tasks.submit_review(id, decision="approved", reason=reason, reviewer_type="human")
        click.echo(f"Approved task {id}: decision={r.decision}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--reason", required=True, help="Reason for rejection (required)")
@click.pass_context
def reject(ctx, id, reason):
    """Reject a task (shortcut for review --decision changes_requested)."""
    client = ctx.obj["client"]
    try:
        r = client.tasks.submit_review(id, decision="changes_requested", reason=reason, reviewer_type="human")
        click.echo(f"Rejected task {id}: decision={r.decision}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--reason", default="", help="Reason for blocking")
@click.pass_context
def block(ctx, id, reason):
    """Block a task."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.block(id, reason=reason)
        click.echo(f"Blocked task {id} -> {t.status}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.pass_context
def unblock(ctx, id):
    """Unblock a task."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.unblock(id)
        click.echo(f"Unblocked task {id} -> {t.status}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.pass_context
def defer(ctx, id):
    """Defer a task."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.defer(id)
        click.echo(f"Deferred task {id} -> {t.status}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.pass_context
def cancel(ctx, id):
    """Cancel a task."""
    client = ctx.obj["client"]
    try:
        t = client.tasks.cancel(id)
        click.echo(f"Cancelled task {id} -> {t.status}")
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@task.command()
@click.argument("id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(ctx, id, yes):
    """Delete a task."""
    if not yes:
        click.confirm(f"Delete task {id}?", abort=True)
    client = ctx.obj["client"]
    try:
        client.tasks.delete(id)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Deleted task {id}")


@task.command()
@click.argument("id")
@click.option("--title", default=None, help="Task title")
@click.option("--description", default=None, help="Task description")
@click.option("--labels", default=None, help="Comma-separated labels")
@click.option("--spec", default=None, help="Task spec text")
@click.option("--spec-file", default=None, type=click.Path(exists=True), help="Read spec from file")
@click.option("--agent-model", default=None, help="Agent model override")
@click.option("--judge/--no-judge", default=None, help="Enable/disable judge review")
@click.option("--isolation", default=None, help="Isolation mode")
@click.option("--workplan", default=None, help="Workplan ID")
@click.option("--milestone", default=None, help="Milestone ID")
@click.option("--acceptance-criteria", default=None, help="JSON array of criteria")
@click.option("--requires", default=None,
              help="DEPRECATED for capability tags — use --required-tags. "
                   "Comma-separated task IDs for dep refs (wrapped as TaskRef).")
@click.option("--required-tags", "required_tags", default=None,
              help="Comma-separated capability tags the claiming agent must have")
@click.option("--test-command", default=None, help="JSON test command dict")
@click.option("--needs-review-before-start/--no-review-before-start", default=None, help="Require review before start")
@click.option("--needs-review-on-completion/--no-review-on-completion", default=None, help="Require review on completion")
@click.pass_context
def update(ctx, id, title, description, labels, spec, spec_file, agent_model, judge, isolation,
           workplan, milestone, acceptance_criteria, requires, required_tags, test_command,
           needs_review_before_start, needs_review_on_completion):
    """Update task fields."""
    kwargs = {}
    if title is not None:
        kwargs["title"] = title
    if description is not None:
        kwargs["description"] = description
    if labels is not None:
        kwargs["labels"] = [l.strip() for l in labels.split(",")]
    if spec is not None:
        kwargs["spec"] = spec
    if spec_file is not None:
        with open(spec_file) as f:
            kwargs["spec"] = f.read()
    if agent_model is not None:
        kwargs["agent_model"] = agent_model
    if judge is not None:
        kwargs["judge"] = judge
    if isolation is not None:
        kwargs["isolation"] = isolation
    if workplan is not None:
        kwargs["workplan"] = workplan
    if milestone is not None:
        kwargs["milestone"] = milestone
    if acceptance_criteria is not None:
        try:
            kwargs["acceptance_criteria"] = json.loads(acceptance_criteria)
        except json.JSONDecodeError:
            click.echo("Error: --acceptance-criteria has invalid JSON", err=True)
            raise SystemExit(1)
    if requires is not None:
        items = [t.strip() for t in requires.split(",") if t.strip()]
        # Heuristic: bare strings that don't look like task IDs are almost
        # certainly capability tags from the pre-0014 era. Steer the user
        # to --required-tags rather than silently writing the wrong field.
        if items and not all(it.startswith(("tsk-", "tsk_")) for it in items):
            click.echo(
                "Warning: --requires now expects task IDs (e.g. 'tsk-abc') for "
                "dependency refs. For capability tags, use --required-tags. "
                "Sending values to required_tags. (vtaskforge#4)",
                err=True,
            )
            kwargs["required_tags"] = items
        else:
            kwargs["requires"] = [{"id": it} for it in items]
    if required_tags is not None:
        kwargs["required_tags"] = [t.strip() for t in required_tags.split(",") if t.strip()]
    if test_command is not None:
        try:
            kwargs["test_command"] = json.loads(test_command)
        except json.JSONDecodeError:
            click.echo("Error: --test-command has invalid JSON", err=True)
            raise SystemExit(1)
    if needs_review_before_start is not None:
        kwargs["needs_review_before_start"] = needs_review_before_start
    if needs_review_on_completion is not None:
        kwargs["needs_review_on_completion"] = needs_review_on_completion

    if not kwargs:
        click.echo("Error: no fields to update. Use --title, --description, --labels, etc.", err=True)
        raise SystemExit(1)

    client = ctx.obj["client"]
    try:
        client.tasks.update(id, **kwargs)
    except VtfError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Updated task {id}")
