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


SOURCE_KINDS = {"vault", "literal"}
VAULT_SCOPES = {"project", "shared"}


def validate_task_variables(variables, project) -> list[str]:
    """Validate a task's `variables:` spec at admission. Returns error strings.

    Empty list = valid. Checks (no Vault round-trip — that's pre-spawn / C.3):
      1. Schema — `name`; `source.kind` in {vault, literal}; vault `scope` in
         {project, shared}; no `path:` on a vault source; literal needs `value`;
         a target must bind env and/or file.
      2. Required-set coverage — every project-scoped vault variable name is
         declared as an EXECUTOR `ProjectVariable` (the always-running consumer;
         judge-role + shared coverage is authoritative at pre-spawn, C.3).
      3. Binding-collision — no two variables share a `target.env` or
         `target.file` (default binding is `env = name`).
    """
    errors: list[str] = []
    if not variables:
        return errors
    if not isinstance(variables, list):
        return ["variables must be a list"]

    env_bindings: dict[str, str] = {}
    file_bindings: dict[str, str] = {}
    needs_coverage: list[str] = []

    for i, entry in enumerate(variables):
        loc = f"variables[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{loc}: must be a mapping")
            continue
        name = entry.get("name")
        if not name or not isinstance(name, str):
            errors.append(f"{loc}: 'name' is required")
            continue

        if "optional" in entry and "required" in entry:
            errors.append(f"{loc} ({name}): specify only one of 'optional'/'required'")

        # --- source ---
        source = entry.get("source") or {}
        if not isinstance(source, dict):
            errors.append(f"{loc} ({name}): 'source' must be a mapping")
            source = {}
        kind = source.get("kind", "vault")
        if kind not in SOURCE_KINDS:
            errors.append(f"{loc} ({name}): source.kind must be one of {sorted(SOURCE_KINDS)}")
        if kind == "vault":
            if "path" in source:
                errors.append(
                    f"{loc} ({name}): 'path' is not allowed on a vault source "
                    f"(the Vault path is convention-derived, never declared)"
                )
            scope = source.get("scope", "project")
            if scope not in VAULT_SCOPES:
                errors.append(f"{loc} ({name}): source.scope must be one of {sorted(VAULT_SCOPES)}")
            elif scope == "project":
                needs_coverage.append(name)
        elif kind == "literal" and "value" not in source:
            errors.append(f"{loc} ({name}): a literal source requires 'value'")

        # --- target / bindings ---
        if "target" not in entry:
            env, file_path = name, None  # default binding: env = name
        else:
            target = entry.get("target") or {}
            if not isinstance(target, dict):
                errors.append(f"{loc} ({name}): 'target' must be a mapping")
                target = {}
            env = target.get("env")
            file_path = target.get("file")
            if env is None and file_path is None:
                errors.append(f"{loc} ({name}): target must specify 'env' and/or 'file'")

        if env:
            if env in env_bindings:
                errors.append(
                    f"{loc} ({name}): target.env '{env}' collides with variable '{env_bindings[env]}'"
                )
            else:
                env_bindings[env] = name
        if file_path:
            if file_path in file_bindings:
                errors.append(
                    f"{loc} ({name}): target.file '{file_path}' collides with variable '{file_bindings[file_path]}'"
                )
            else:
                file_bindings[file_path] = name

    # --- required-set coverage (executor role) ---
    if needs_coverage and project is not None:
        from .models import ProjectVariable

        declared = set(
            ProjectVariable.objects.filter(
                project=project, role="executor", name__in=needs_coverage
            ).values_list("name", flat=True)
        )
        for name in needs_coverage:
            if name not in declared:
                errors.append(
                    f"variable '{name}' is not declared as an executor ProjectVariable for this project"
                )

    return errors
