# C.2 Implementation Plan — vtaskforge variables substrate (schema + admission)

> Status: **PLAN — for review, no code landed yet** (2026-05-29).
> Parent design: `viloforge-platform/docs/vtaskforge-variables-DESIGN.md`.
> This is phasing **stage 2** ("vtaskforge schema + admission — can land second; no
> functional change yet, empty tables"). C.1 (Vault policies + K8s auth roles + chart
> SAs) is already live in vafi-dev. C.3 (vafi controller code) is a separate effort.

## Scope of C.2 (this plan)

From the design's §Implementation plan → `vilosource/vtaskforge`:

- **Models + migrations**: `ProjectVariable`, `VariableAudit`, `Task.secrets_snapshot` JSONField.
- **Validation**: `Project.id` K8s-safe regex (admission on project create); `TaskSerializer.validate()`
  for schema, required-set coverage, and binding-collision.
- **DRF API**: `ProjectVariableViewSet` (create/list/destroy/partial_update) with near-match warning + `?force=true`.
- **CLI**: `vtf project var add/list/show/update/remove` + `vtf task lint`.

### Explicitly OUT of C.2 scope
- `ProjectConfig` model — design defers to "out of scope for v1".
- All vafi controller code (`SecretBackend`, `VaultBackend`, materializer, pre-spawn validation,
  `secrets_snapshot` *population*) — that's C.3.
- `vtf project var probe` — the design states this is exposed by the **vafi controller**
  (`POST /admin/probe`), not vtaskforge, because it needs the TokenRequest+Vault path. Not C.2.
- Populating `secrets_snapshot` (spawn-time, vafi) — C.2 only adds the nullable field.

---

## Open questions — need decisions before the affected slice

### Q1 — RESOLVED (2026-05-30): immutable validated `Project.slug`
**Decision: add an immutable, validated `Project.slug` as the project's operational identity; keep the
nanoid as the opaque PK; use the slug as the Vault-path segment from α onward.**

Verified facts that forced this:
- `generate_nanoid()` calls `nanoid.generate(size=21)` with **no custom alphabet** → python-nanoid's default
  64-char URL-safe alphabet (`A-Za-z0-9_-`). Existing PKs contain uppercase/`_`/leading-trailing `-` and
  **cannot** be a K8s ServiceAccount-name suffix.
- The β Vault policy derives the path segment *from the SA name*:
  `…/projects/{{… service_account_name | trim_prefix "vtaskforge-executor-"}}/executor/*`. So the path
  segment **=== the SA-name suffix === a K8s-safe string.** A K8s-safe identifier is mandatory, not optional.

Why a separate slug (rejecting the alternatives):
- **(B/D) make the PK K8s-safe** — overloads the immutable FK-target PK with a human-renameable concern, and
  can't fix existing (non-conforming) PKs anyway.
- **(C) hash/sanitize in vafi** — destroys the human-greppable paths the design values, moves enforcement to
  spawn time (the design says validate at *admission* time, "not at vafi pod-spawn time — too late"), and
  risks sanitization collisions.
- **(A) separate slug** — clean separation (opaque PK vs human identity), validated at creation, human-meaningful,
  β-ready. Industry-standard (Stripe id+nickname, GitHub id+login, k8s uid+name).

**Zero-migration α→β:** α uses one shared SA + a project-agnostic wildcard policy (`…/projects/+/executor/*`)
with controller-discipline isolation; β swaps to the per-slug templated policy. Because the Vault path is
**always** `…/projects/<slug>/…`, promotion is a policy change with **no secret re-pathing**. Using the slug
in the path from α is the only choice that keeps β promotion free.

slug spec:
- `CharField(unique=True)`, `RegexValidator(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")`, **≤63 chars** (RFC 1123
  *label* — stricter than the design's 200/subdomain, on purpose: keeps the slug usable as a namespace/label
  in any future topology, at zero practical cost. Flag if you'd rather honor the doc's 200.).
- **Immutable after creation** (changing it orphans Vault secrets + breaks the SA binding; a rename is a
  deliberate migration, not a field edit). Display `name` stays freely editable.
- Auto-derived from `name` (slugify + dedupe suffix) on create, human-overridable.

What uses slug vs PK:
- DB FKs (`ProjectVariable.project`, `VariableAudit.project`, `Task.project`) → **nanoid PK** (unchanged).
- Vault path segment, β SA suffix (`vtaskforge-executor-<slug>`), operator commands (`vtf … <slug>`),
  `VariableAudit.vault_path` → **slug**. vafi (C.3) resolves `task.project.slug` at spawn.
- API project lookup accepts **slug-or-PK** (operators type `abad`; programmatic uses the nanoid).

**Backfill is free** — greenfield substrate (no ProjectVariable rows, no Vault paths exist) → slug backfill for
existing projects is a pure DB populate (slugify each `name`, dedupe), zero secret relocation.

**C.3 contract implication:** vafi's spawn path and SA-name derivation key on `project.slug`, not the PK.
**Slice-1 verification step:** confirm the *live* α Vault policy for `vtaskforge-executor`/`-judge` uses a
project-agnostic wildcard at the project segment (`…/projects/+/<role>/*`), so slug-in-path is genuinely
zero-migration to β. (Cheap Vault read; do it when Slice 1 starts.)

### Q2 — New `variables` app vs extending `tasks`
Design allows either. **Recommendation: new `variables` Django app** (`src/variables/`) housing
`ProjectVariable` + `VariableAudit`. `Task.secrets_snapshot` is a field on the existing `tasks` app
(separate small migration). Rationale: variables are project-scoped and conceptually distinct from tasks;
a dedicated app keeps migrations/serializers/tests cohesive and mirrors the existing per-app layout.

### Q3 — v1/v2 serializer parity
The codebase splits `serializers.py` (v1) / `serializers_v2.py` (v2), and root urls mount every app under
both `/v1/` and `/v2/`. `ProjectVariable` has **no actor/user FKs**, so v1 and v2 representations are
identical. **Recommendation: one `ProjectVariableSerializer`** registered for both versions (no v2 variant
needed); revisit only if a computed/permission field is later added.

### Q4 — `VariableAudit` write path in C.2?
The design has vafi (C.3) "emit `VariableAudit` rows via the vtaskforge API." C.2 lands the **model**;
the **write endpoint** it consumes is logically C.2 (so C.3 has something to call). **Recommendation:**
land the model in Slice 1 and a minimal create-only `VariableAudit` endpoint in Slice 4 (service-token
auth, controller-only), explicitly read-mostly for now. **Confirm** whether you want the endpoint in C.2
or deferred to land with its C.3 consumer.

### Q5 — `vtf task lint` data source
`vtf task lint <spec.yaml>` does **local** fuzzy-match (Levenshtein ≤2 or 25% of name length) of declared
variable names against the project's `ProjectVariable` schema. It needs to fetch the project's variable
list (the `GET /projects/{id}/variables` from Slice 3) and run matching client-side. **Recommendation:**
ship `vtf task lint` in Slice 5 (CLI), after the list endpoint exists.

---

## Slice breakdown (each slice = one PR, test-first)

### Slice 1 — Data model + migrations (foundation, no API)
**New app `variables`:**
- `ProjectVariable(ProjectScopedModel, TimestampMixin)`:
  - `project = FK(projects.Project, on_delete=PROTECT)`, `name` (text), `role` (choices: executor|judge),
    `scope` (choices: project|shared, default project), `description` (text, null), `required` (bool, default True).
  - `class Meta: unique_together = (("project", "name", "role"),)` (the design's composite PK; expressed as a
    unique constraint since the model keeps the conventional surrogate key / or use the composite explicitly —
    see note).
  - `project_filter_path = "project_id"`, `get_project_id(self) -> str: return self.project_id`.
  - **Note**: the design writes `PRIMARY KEY (project_id, name, role)`. Django ModelViewSet/routing is far
    smoother with a single-column PK + a `unique_together`. **Recommendation:** surrogate nanoid PK
    (`NanoIDMixin`) + `unique_together(project, name, role)`. Functionally identical; keeps DRF detail routes simple.
- `VariableAudit` (write-once audit; matches design §Data model):
  - `audit_id` (UUID PK), `timestamp`, `task = FK(tasks.Task, PROTECT, null)`, `project = FK(projects.Project, PROTECT)`,
    `variable_name`, `variable_scope` (project|shared), `vault_path`, `vault_version` (int, null),
    `result` (success|not_found|empty|unreachable|permission_denied), `size_bytes` (int, null),
    `duration_ms` (int), `controller_id` (text).
  - **Never** stores the value/hash/prefix — enforce by schema (no such field) + a serializer guard.
**tasks app migration:**
- `Task.secrets_snapshot = JSONField(null=True, blank=True)` — `{ variable_name: vault_version }`, populated by vafi (C.3).

**Migrations:** `makemigrations variables` + `makemigrations tasks` via docker compose; both are additive
(new app tables + one nullable column) → safe, no backfill, no downtime. Empty-table semantics = no behavior change.

**Tests (`tests/variables/test_models.py`, `tests/tasks/test_models.py`):**
- ProjectVariable: create minimal; defaults (`scope=project`, `required=True`); `unique_together` violation
  (same project+name+role → IntegrityError); same name across executor/judge allowed; `get_project_id()` returns FK.
- VariableAudit: create with each `result` value; PK is UUID; no value/hash field exists (introspection assert).
- Task: `secrets_snapshot` defaults to None; round-trips a JSON dict.
- Add `ProjectVariableFactory` + `VariableAuditFactory` to `tests/factories.py`.

### Slice 2 — `Project.slug` K8s-safe identity (admission on project create) — *Q1 RESOLVED*
- Add `Project.slug = CharField(max_length=63, unique=True, validators=[RegexValidator(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")])`.
- `ProjectSerializer`/`ProjectV2Serializer`: surface `slug`; **auto-derive from `name`** (slugify + dedupe
  suffix) when not supplied; **immutable on update** (read-only after create — reject/ignore changes).
- Project lookup (in ProjectViewSet + the nested variables routes) resolves **slug-or-PK**.
- Migration sequence (the only non-trivial migration in C.2): (1) add `slug` nullable; (2) data migration
  backfilling every existing project (`slugify(name)`, dedupe, fallback `project-<shorthash>` if empty/too long);
  (3) enforce `NOT NULL` + `unique`. Free of secret-relocation (greenfield substrate).
**Tests (`tests/projects/test_api.py`, `test_models.py`):** valid slug accepted; uppercase / underscore /
leading-or-trailing hyphen / >63 rejected (400); auto-derivation from `name`; dedupe on collision; slug immutable
on PATCH (change ignored/rejected); duplicate slug rejected; slug-or-PK lookup resolves the same project; data
migration backfills existing rows to valid unique slugs.

### Slice 3 — `ProjectVariableViewSet` (CRUD API) + routing
- `variables/serializers.py`: `ProjectVariableSerializer` (Meta fields; `project` read-only from URL/context;
  `read_only_fields=[created_at,updated_at]`).
- `variables/views.py`: `ProjectVariableViewSet(TrackAccessMixin, ModelViewSet)`,
  `permission_classes=[IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]`,
  `http_method_names=[get, post, patch, delete, head, options]` (no PUT — matches Project/Task convention).
  - `get_queryset`: filter by URL `project_id`; `scope_queryset_to_user_projects` for list.
  - **Near-match warning + `?force=true`** on `create`: if the new `name` is within Levenshtein ≤2 (or 25% of
    name length) of an existing variable name for the same (project, role), reject 400 with a "did you mean…"
    payload unless `?force=true`. (Shared Levenshtein helper reused by `vtf task lint`.)
  - `destroy`: 204 hard delete. (Reference-warning scan of referencing task specs deferred to Slice 4/5 when
    the `variables:` task-spec field exists.)
  - `partial_update`: only `description`, `required`, `scope` mutable; `name`/`role` immutable (400 if changed).
  - **DECISION (2026-05-30):** detail routes address variables by their **surrogate PK** (`.../variables/<pk>/`),
    NOT by `{name}` as sketched above — a name is not unique without the role (`(project, name, role)`), so PK
    addressing is unambiguous. The CLI (Slice 5) resolves `name` (+ `role`) → PK via a list call. Parent project
    is resolved by **slug-or-PK**. Exact-duplicate is checked explicitly in `create()` (project is URL-bound, so
    DRF can't attach a UniqueTogetherValidator). Project-scoping uses `scope_queryset_to_user_projects` (staff
    bypass applies, as everywhere); a non-member is scoped out (404).
- `variables/urls.py`: nested route `path("projects/<str:project_id>/variables/...")` per the existing nesting
  convention (like `projects/{id}/members/`). Either a router on a nested basename or explicit `APIView`s —
  **recommend** routing the ViewSet with a `project_id` URL kwarg + a small mixin to inject it, matching members.
- Register in root urls under both `/v1/` and `/v2/`.
**Tests (`tests/variables/test_api.py`):** create 201; list scoped to project + role filter; duplicate
(project,name,role) → 400; near-match without force → 400 with suggestion; near-match with `?force=true` → 201;
PATCH description ok / PATCH name rejected; DELETE 200 + reference warning; cross-project isolation (user
without membership → 403/empty); unauth → 401.

### Slice 4 — `TaskSerializer.validate()` admission rules (+ VariableAudit endpoint per Q4)
- Extend `TaskSerializer.validate()` / `TaskV2Serializer.validate()` (and a shared helper) to validate the
  optional `variables:` spec field at task submit:
  1. **Schema/format**: each entry has `name`; optional `source`/`target`/`required|optional`; `source.kind ∈
     {vault, literal}`; vault `scope ∈ {project, shared}`; literal has `value`; **no `path:` on vault** (reject).
  2. **Required-set coverage**: every declared `name` exists as a `ProjectVariable` for that (project, role).
     *(Role: the design ties role to the spawning pod; at admission, validate against the task's target role
     — confirm how role is known at submit; if a task can run as both, validate against both sets. Flag if
     the task model doesn't yet carry a role discriminator.)*
  3. **Binding-collision**: reject if two variables resolve to the same `target.env` or `target.file.path`
     (defaults: `target.env = name`). Returns 400 `ValidationError`.
  - No Vault round-trip (cheap, server-side) — matches design §Admission layer 2.
- (Q4) `VariableAuditViewSet` create-only endpoint (service-token/controller auth) — model already exists from Slice 1.
**Tests (`tests/tasks/test_api.py` + `tests/variables/test_admission.py`):** task with unknown variable → 400
required-set; duplicate `target.env` → 400 collision; `path:` on vault source → 400; valid spec → 201; empty/absent
`variables:` → 201 (backward-compat, byte-identical behavior); literal source ok.

### Slice 5 — CLI (`vtf project var …` + `vtf task lint`)
- `cli/vtf/commands/project.py`: new `@click.group() var`, registered as **`project.add_command(var)`** →
  `vtf project var add|list|show|update|remove`. Wraps a new SDK manager.
- `vtf-sdk-python/vtf_sdk/`: add `ProjectVariableManager` (+ `entities.py` `ProjectVariable`) and wire into `VtfClient`.
- `cli/vtf/commands/task.py`: `vtf task lint <spec.yaml>` — load YAML, fetch project variable list, run local
  Levenshtein fuzzy match (shared threshold with Slice 3), report unknown/near-miss names + binding collisions;
  exit non-zero on hard errors, warn on near-misses.
**Tests (`cli/tests/test_project_commands.py`, `test_task_commands.py`):** CliRunner + mocked client for each
subcommand (add/list/show/update/remove success + error paths); `task lint` clean spec, unknown-name, near-miss,
collision; SDK manager unit tests.

---

## Migration strategy
- All migrations are **additive and empty-state**: new `variables` app tables + one nullable `Task` column +
  (Slice 2) a nullable-then-enforced `Project.slug`. No data migration except the **Project.slug backfill** for
  existing projects (Q1/A) — handle as: add nullable → backfill (derive a slug from name, dedupe) → enforce
  not-null+unique in a follow-up migration. Per the design, empty `ProjectVariable` tables mean zero behavior
  change for existing tasks (the backward-compat acceptance criterion).
- Apply via `docker compose exec api python src/manage.py makemigrations <app>` then `migrate`; dogfood via the
  `docker-compose.dogfood.yml` variant. Each slice's migration ships in its own PR.

## Sequencing & PR strategy
1. Slice 1 (models) — no API surface; safe to merge immediately.
2. Slice 2 (slug/validation) — **gated on Q1**.
3. Slice 3 (CRUD API) — depends on Slice 1.
4. Slice 4 (admission) — depends on Slices 1+3.
5. Slice 5 (CLI) — depends on Slice 3 (and Slice 4 for `lint`'s collision check).
Each PR is test-first (pytest under `tests/<app>/`, CLI under `cli/tests/`), green CI before merge. None of
1–5 changes runtime behavior for tasks without a `variables:` block (the design's stage-2 guarantee).

## Acceptance criteria (whole of C.2)
- All five slices merged with passing tests; `pytest` green for backend + CLI.
- A project can declare executor/judge variables via API + CLI; duplicates and near-misses are caught;
  task specs referencing unknown variables or colliding bindings are rejected at submit with clear 400s.
- Tasks **without** a `variables:` block are unaffected (byte-identical admission behavior).
- `secrets_snapshot` field exists (nullable), ready for vafi/C.3 to populate.
- No Vault round-trips anywhere in C.2 (that's C.3).
