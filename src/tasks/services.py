"""
Task service functions — reusable business logic extracted from views.
"""
from links.models import Link
from tasks.models import Task


def resolve_dependencies(task_id: str) -> dict:
    """Check if all depends_on links for a task point to done tasks.

    Returns a dict with:
        resolved (bool): True if all dependencies are satisfied.
        dependencies (list): All dependency info dicts with id, title, status.
        unresolved (list): Subset of dependencies that are not done.

    External dependencies (target task not found in DB) are skipped — they do
    not block resolution, consistent with the inline claim() behaviour.
    """
    depends_on_links = Link.objects.filter(
        source_type="task", source_id=task_id, link_type="depends_on"
    )

    dependencies = []
    unresolved = []

    for link in depends_on_links:
        try:
            dep_task = Task.objects.get(pk=link.target_id)
        except Task.DoesNotExist:
            # External / dangling reference — skip (not treated as blocking)
            continue

        dep_info = {
            "id": dep_task.id,
            "title": dep_task.title,
            "status": dep_task.status,
        }
        dependencies.append(dep_info)
        if dep_task.status != "done":
            unresolved.append(dep_info)

    return {
        "resolved": len(unresolved) == 0,
        "dependencies": dependencies,
        "unresolved": unresolved,
    }


def get_tasks_with_unresolved_deps(task_ids: list) -> set:
    """Given a list of task IDs, return the subset that have unresolved dependencies.

    A task has unresolved deps when at least one of its depends_on link targets
    exists in the DB and is not in 'done' status. Tasks whose dependency links
    all point to external/nonexistent targets are considered resolved.

    Used by claimable() to efficiently filter out tasks that cannot yet be claimed.
    """
    if not task_ids:
        return set()

    # Only look at task IDs that actually have depends_on links
    task_ids_with_deps = set(
        Link.objects.filter(
            source_type="task",
            source_id__in=task_ids,
            link_type="depends_on",
        ).values_list("source_id", flat=True)
    )

    unresolved_ids = set()
    for tid in task_ids_with_deps:
        result = resolve_dependencies(tid)
        if not result["resolved"]:
            unresolved_ids.add(tid)

    return unresolved_ids
