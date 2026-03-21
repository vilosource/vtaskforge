"""
Review flag cascading policy.

Determines the effective review flags for a task by cascading:
    task -> milestone -> workplan

A task-level flag (even if False) always overrides milestone/workplan.
Milestone-level None means "fall through to workplan".
Workplan defaults are never null (BooleanField with default=False).
"""


def get_effective_review_flags(task) -> tuple[bool, bool]:
    """Return (needs_review_before_start, needs_review_on_completion).

    Cascade: task -> milestone -> workplan. Defaults to False if all null.
    Task flag=False OVERRIDES milestone/workplan flag=True.

    With optional milestone/workplan:
    - If task has milestone + workplan: Task -> Milestone -> Workplan (unchanged)
    - If task has workplan only: Task -> Workplan (skip milestone)
    - If task has neither (backlog): Task only — no cascading, defaults to False
    """
    # before_start
    if task.needs_review_before_start is not None:
        before_start = task.needs_review_before_start
    elif task.milestone and task.milestone.default_needs_review_before_start is not None:
        before_start = task.milestone.default_needs_review_before_start
    elif task.workplan:
        before_start = task.workplan.default_needs_review_before_start or False
    else:
        before_start = False

    # on_completion
    if task.needs_review_on_completion is not None:
        on_completion = task.needs_review_on_completion
    elif task.milestone and task.milestone.default_needs_review_on_completion is not None:
        on_completion = task.milestone.default_needs_review_on_completion
    elif task.workplan:
        on_completion = task.workplan.default_needs_review_on_completion or False
    else:
        on_completion = False

    return (before_start, on_completion)
