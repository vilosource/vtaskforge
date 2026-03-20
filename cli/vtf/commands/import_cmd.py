import yaml
import click
from pathlib import Path
from vtf.client import VTFAPIError


@click.command("import")
@click.argument("phase_dir", type=click.Path(exists=True))
@click.option("--workplan", default=None, help="Import into existing workplan ID")
@click.option("--dry-run", is_flag=True, help="Validate without creating")
@click.pass_context
def import_cmd(ctx, phase_dir, workplan, dry_run):
    """Import a phase directory into vtaskforge."""
    phase_path = Path(phase_dir)
    client = ctx.obj["client"]

    # Read PHASE.md for metadata (extract name from first # heading)
    phase_md = phase_path / "PHASE.md"
    phase_name = phase_path.name
    phase_description = ""
    if phase_md.exists():
        content = phase_md.read_text()
        lines = content.strip().split("\n")
        for line in lines:
            if line.startswith("# "):
                phase_name = line[2:].strip()
                break
        phase_description = content

    # Read dag.yaml for dependencies (authoritative source)
    dag_file = phase_path / "dag.yaml"
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
    tasks_dir = phase_path / "tasks"
    task_specs = []
    if tasks_dir.exists():
        for yaml_file in sorted(tasks_dir.glob("*.yaml")):
            with open(yaml_file) as f:
                spec = yaml.safe_load(f)
                if spec:
                    task_specs.append(spec)

    # Determine the phase ref from directory name
    phase_ref = phase_path.name.replace(" ", "-").lower()

    # Build task list and ref map
    task_refs = {}
    phase_tasks = []
    for spec in task_specs:
        task_id = str(spec["id"])
        ref = f"task-{task_id}"
        task_refs[task_id] = ref
        task_entry = {
            "ref": ref,
            "title": spec["name"],
            "description": spec.get("description", ""),
            "acceptance_criteria": spec.get("acceptance_criteria", []),
        }
        phase_tasks.append(task_entry)

    # Build dependency links from dag.yaml (dag is authoritative)
    links = []
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

    # Build bulk import payload
    payload = {
        "workplan": {
            "name": phase_name,
            "description": phase_description,
        },
        "phases": [{
            "ref": phase_ref,
            "name": phase_name,
            "description": phase_description,
            "tasks": phase_tasks,
        }],
        "links": links,
    }

    if workplan:
        payload["workplan_id"] = workplan

    if dry_run:
        click.echo("Dry run — payload that would be sent:")
        click.echo(yaml.dump(payload, default_flow_style=False))
        click.echo(f"\nWould create: 1 workplan, 1 phase, {len(phase_tasks)} tasks, {len(links)} links")
        return

    try:
        result = client.post("/v1/bulk/import", payload)
        ref_map = result.get("ref_map", {})
        click.echo("Import successful!")
        click.echo(f"Workplan: {ref_map.get('workplan', 'N/A')}")
        click.echo(f"Phase:    {ref_map.get(phase_ref, 'N/A')}")
        click.echo("\nTasks:")
        for spec in task_specs:
            task_id = str(spec["id"])
            ref = task_refs[task_id]
            created_id = ref_map.get(ref, "N/A")
            click.echo(f"  {task_id} ({spec['name']}): {created_id}")
    except VTFAPIError as e:
        click.echo(f"Import failed: {e}", err=True)
        raise SystemExit(1)
