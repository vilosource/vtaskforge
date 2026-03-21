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
    """
    # before_start
    if task.needs_review_before_start is not None:
        before_start = task.needs_review_before_start
    elif task.milestone.default_needs_review_before_start is not None:
        before_start = task.milestone.default_needs_review_before_start
    else:
        before_start = task.workplan.default_needs_review_before_start or False

    # on_completion
    if task.needs_review_on_completion is not None:
        on_completion = task.needs_review_on_completion
    elif task.milestone.default_needs_review_on_completion is not None:
        on_completion = task.milestone.default_needs_review_on_completion
    else:
        on_completion = task.workplan.default_needs_review_on_completion or False

    return (before_start, on_completion)
