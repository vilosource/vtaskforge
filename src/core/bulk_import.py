from django.db import transaction

from links.models import Link
from tasks.models import Task
from workplans.models import Phase, Workplan


def _infer_ref_type(ref, ref_map, ref_type_map):
    """Return the entity type string for a ref."""
    return ref_type_map.get(ref)


def perform_bulk_import(payload):
    """
    Create workplan structure atomically.

    Returns dict mapping refs to created nanoid IDs. On any error the
    transaction is rolled back automatically.
    """
    ref_map = {}
    # Track what type each ref maps to so we can set source_type/target_type on links.
    ref_type_map = {}

    with transaction.atomic():
        # 1. Validate duplicate refs upfront
        all_refs = []
        for phase_data in payload.get("phases", []):
            all_refs.append(phase_data["ref"])
            for task_data in phase_data.get("tasks", []):
                all_refs.append(task_data["ref"])

        seen = set()
        for ref in all_refs:
            if ref in seen:
                raise ValueError(f"Duplicate ref: {ref}")
            seen.add(ref)

        # 2. Create or use existing workplan
        workplan_id = payload.get("workplan_id")
        if workplan_id:
            try:
                workplan = Workplan.objects.get(pk=workplan_id)
            except Workplan.DoesNotExist:
                raise ValueError(f"Workplan not found: {workplan_id}")
        else:
            wp_data = payload.get("workplan", {})
            if not wp_data.get("name"):
                raise ValueError("workplan.name is required when workplan_id is not provided")
            workplan = Workplan.objects.create(
                name=wp_data["name"],
                description=wp_data.get("description", ""),
                tags=wp_data.get("tags", []),
            )
        ref_map["workplan"] = workplan.id
        ref_type_map["workplan"] = "workplan"

        # 3. Create phases and their nested tasks
        for phase_data in payload.get("phases", []):
            ref = phase_data["ref"]
            phase = Phase.objects.create(
                workplan=workplan,
                name=phase_data["name"],
                description=phase_data.get("description", ""),
            )
            ref_map[ref] = phase.id
            ref_type_map[ref] = "phase"

            for task_data in phase_data.get("tasks", []):
                task_ref = task_data["ref"]
                task = Task.objects.create(
                    phase=phase,
                    workplan=workplan,
                    title=task_data["title"],
                    description=task_data.get("description", ""),
                    acceptance_criteria=task_data.get("acceptance_criteria", []),
                    requires=task_data.get("requires", []),
                    spec=task_data.get("spec", ""),
                    agent_model=task_data.get("agent_model", ""),
                    test_command=task_data.get("test_command", {}),
                    judge=task_data.get("judge", False),
                    isolation=task_data.get("isolation", "sequential"),
                )
                ref_map[task_ref] = task.id
                ref_type_map[task_ref] = "task"

        # 4. Validate all link refs resolve before creating anything
        for link_data in payload.get("links", []):
            source_ref = link_data["source_ref"]
            target_ref = link_data["target_ref"]
            if source_ref not in ref_map:
                raise ValueError(f"Unresolved source_ref: {source_ref}")
            if target_ref not in ref_map:
                raise ValueError(f"Unresolved target_ref: {target_ref}")

        # 5. Create links
        for link_data in payload.get("links", []):
            source_ref = link_data["source_ref"]
            target_ref = link_data["target_ref"]
            Link.objects.create(
                source_type=ref_type_map[source_ref],
                source_id=ref_map[source_ref],
                target_type=ref_type_map[target_ref],
                target_id=ref_map[target_ref],
                link_type=link_data.get("type", "depends_on"),
            )

    return ref_map
