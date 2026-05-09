"""
Pure helper for splitting Task.requires (historically overloaded) into
(requires_deps, required_tags). Lives outside services.py so the
0014 migration can call it without dragging the rest of services.

Bare strings -> required_tags
Dict-shaped  -> requires (TaskRef-style dep entries)
Other shapes -> dropped (best-effort; should not occur in practice)
"""


def partition_requires(value):
    """Return (deps, tags) lists from a JSONField `requires` value.

    >>> partition_requires([])
    ([], [])
    >>> partition_requires(["executor", "pi"])
    ([], ['executor', 'pi'])
    >>> partition_requires([{"id": "t1"}, {"id": "t2"}])
    ([{'id': 't1'}, {'id': 't2'}], [])
    >>> partition_requires(["executor", {"id": "t1"}])
    ([{'id': 't1'}], ['executor'])
    >>> partition_requires(None)
    ([], [])
    >>> partition_requires("oops")  # not a list — defensive fallback
    ([], [])
    """
    if not isinstance(value, list):
        return [], []
    deps = []
    tags = []
    for entry in value:
        if isinstance(entry, str):
            tags.append(entry)
        elif isinstance(entry, dict):
            deps.append(entry)
        # else: drop silently
    return deps, tags
