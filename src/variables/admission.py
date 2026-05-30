"""Cheap, server-side admission helpers for the variables substrate.

Levenshtein-based near-match detection guards against typo'd variable names
(e.g. declaring `GH_TOKE` when `GH_TOKEN` already exists). Threshold is
max(2, 25% of the name length) per the C.2 plan; also reused by `vtf task lint`.
"""


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def near_matches(name: str, existing_names, threshold: int = 2) -> list[str]:
    """Existing names within edit distance of `name` (excluding an exact match)."""
    thr = max(threshold, len(name) // 4)
    return [ex for ex in existing_names if 0 < levenshtein(name, ex) <= thr]
