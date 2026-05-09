import yaml
import click
from pathlib import Path
from vtf_sdk.exceptions import VtfError


@click.command("import")
@click.argument("milestone_dir", type=click.Path(exists=True))
@click.option("--workplan", default=None, help="Import into existing workplan ID")
@click.option("--project", default=None, help="Import into existing project ID")
@click.option("--dry-run", is_flag=True, help="Validate without creating")
@click.pass_context
def import_cmd(ctx, milestone_dir, workplan, project, dry_run):
    """Import a milestone directory into vtaskforge."""
    milestone_path = Path(milestone_dir)
    client = ctx.obj["client"]

    # Read MILESTONE.md for metadata (extract name from first # heading)
    milestone_md = milestone_path / "MILESTONE.md"
    milestone_name = milestone_path.name
    milestone_description = ""
    if milestone_md.exists():
        content = milestone_md.read_text()
        lines = content.strip().split("\n")
        for line in lines:
            if line.startswith("# "):
                milestone_name = line[2:].strip()
                break
        milestone_description = content

    # Read dag.yaml for dependencies (authoritative source)
    dag_file = milestone_path / "dag.yaml"
    dag_tasks = []
    if dag_file.exists():
        with open(dag_file) as f:
            dag_data = yaml.safe_load(f) or {}
        dag_tasks = dag_data.get("tasks", [])

    # Build dependency map from dag.yaml: task_id -> list of dep ids
    dag_deps = {}
    for dag_task in dag_tasks:
        task_id = str(dag_task["id"])
        dag_deps[task_id] = [str(d) for d in dag_task.get("depends_on", [])]

    # Read task YAML files
    tasks_dir = milestone_path / "tasks"
    task_specs = []
    if tasks_dir.exists():
        for yaml_file in sorted(tasks_dir.glob("*.yaml")):
            raw_yaml = yaml_file.read_text()
            with open(yaml_file) as f:
                spec = yaml.safe_load(f)
                if spec:
                    spec["_raw_yaml"] = raw_yaml
                    task_specs.append(spec)

    # Determine the milestone ref from directory name
    milestone_ref = milestone_path.name.replace(" ", "-").lower()

    # Build task list and ref map
    task_refs = {}
    milestone_tasks = []
    for spec in task_specs:
        task_id = str(spec["id"])
        ref = f"task-{task_id}"
        task_refs[task_id] = ref
        task_entry = {
            "ref": ref,
            "title": spec["name"],
            "description": spec.get("description", ""),
            "acceptance_criteria": spec.get("acceptance_criteria", []),
            "requires": spec.get("requires", []),
            "spec": spec.get("_raw_yaml", ""),
            "agent_model": spec.get("agent_model", ""),
            "test_command": spec.get("test_command", {}),
            "judge": spec.get("judge", False),
            "isolation": spec.get("isolation", "sequential"),
        }
        milestone_tasks.append(task_entry)

    if not milestone_tasks:
        if not tasks_dir.exists():
            click.echo(f"Error: no tasks/ directory found in {milestone_path}", err=True)
        else:
            click.echo(f"Error: no valid task YAML files found in {tasks_dir}", err=True)
        click.echo("Hint: task files should be in <milestone>/tasks/*.yaml with 'id' and 'name' fields", err=True)
        raise SystemExit(1)

    # Build dependency links
    # dag.yaml is authoritative when present; fall back to inline depends_on
    links = []
    if dag_deps:
        # Use dag.yaml dependencies
        for task_id, dep_ids in dag_deps.items():
            if task_id not in task_refs:
                continue
            for dep_id in dep_ids:
                if dep_id in task_refs:
                    links.append({
                        "source_ref": task_refs[task_id],
                        "target_ref": task_refs[dep_id],
                        "type": "depends_on",
                    })
    else:
        # Fall back to inline depends_on from task specs
        for spec in task_specs:
            task_id = str(spec["id"])
            if task_id not in task_refs:
                continue
            inline_deps = spec.get("depends_on", [])
            if isinstance(inline_deps, str):
                inline_deps = [inline_deps]
            for dep_id in inline_deps:
                dep_id = str(dep_id)
                if dep_id in task_refs:
                    links.append({
                        "source_ref": task_refs[task_id],
                        "target_ref": task_refs[dep_id],
                        "type": "depends_on",
                    })

    # Build bulk import payload
    payload = {
        "milestones": [{
            "ref": milestone_ref,
            "name": milestone_name,
            "description": "",  # don't dump full MILESTONE.md as description
            "tasks": milestone_tasks,
        }],
        "links": links,
    }

    if project:
        # Add to existing project
        payload["project_id"] = project
    elif workplan:
        # Infer project from the workplan
        try:
            wp = client.workplans.get(workplan)
            payload["project_id"] = wp.project.id if wp.project else None
        except (VtfError, KeyError, AttributeError):
            click.echo(f"Warning: could not look up project for workplan {workplan}, creating new project", err=True)
            payload["project"] = {
                "name": milestone_name,
                "description": "",
            }
    else:
        # Create new project named after the milestone directory
        payload["project"] = {
            "name": milestone_name,
            "description": "",
        }

    if workplan:
        # Add milestone to existing workplan
        payload["workplan_id"] = workplan
    else:
        # Create new workplan named after the milestone directory
        payload["workplan"] = {
            "name": milestone_name,
            "description": milestone_description,
        }

    if dry_run:
        click.echo("Dry run — payload that would be sent:")
        click.echo(yaml.dump(payload, default_flow_style=False))
        what = f"add 1 milestone to workplan {workplan}" if workplan else "create 1 workplan + 1 milestone"
        click.echo(f"\nWould {what}, {len(milestone_tasks)} tasks, {len(links)} links")
        return

    try:
        result = client.bulk.do_import(payload=payload)
        ref_map = result.get("ref_map", {})
        click.echo("Import successful!")
        click.echo(f"Workplan:  {ref_map.get('workplan', 'N/A')}")
        click.echo(f"Milestone: {ref_map.get(milestone_ref, 'N/A')}")
        click.echo("\nTasks:")
        for spec in task_specs:
            task_id = str(spec["id"])
            ref = task_refs[task_id]
            created_id = ref_map.get(ref, "N/A")
            click.echo(f"  {task_id} ({spec['name']}): {created_id}")
    except VtfError as e:
        click.echo(f"Import failed: {e}", err=True)
        raise SystemExit(1)
