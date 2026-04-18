# Project & Repository Model — Provider-Agnostic Design

**Date:** 2026-04-18
**Status:** Draft
**Author:** claude (session 2026-04-18; supersedes `project-bootstrap-DESIGN.md`)
**Supersedes:** `docs/design/project-bootstrap-DESIGN.md`
**Related:**
- `docs/design/project-hierarchy-DESIGN.md` — the current Project model (predates this redesign)
- `docs/design/phase4c-mcp-redesign-DESIGN.md` — MCP tool conventions this design follows
- `docs/design/user-management-DESIGN.md` — identity model we depend on
- `vafi/docs/vtf-vafi-interface-CONTRACT.md` — how vafi executors consume vtf state

---

## 1. Problem

Three structural gaps prevent vtf from supporting real-world project workflows:

1. **A project can only have one repository.** `Project.repo_url` is a scalar column. Real projects have backend + frontend + docs; monorepo → microservices splits; customer forks alongside upstream tracking. The single-repo model forces these into separate vtf Projects even though they're organizationally one unit.

2. **Repositories have no first-class identity.** Auth credentials, clone strategies (SSH deploy key vs HTTPS token vs GitHub App token), branch/depth/submodule options — none of this is modeled. Today it's all implicit via a single cluster-wide `github-ssh` k8s secret, which works only because Viloforge has one auth profile.

3. **The fleet assumes GitHub.** The `github-ssh` secret name, the Claude Code CLI's MCP configuration path, the executor's git-clone logic all hardcode the host. GitLab, Bitbucket, Gitea, or self-hosted git are not reachable without code changes.

Additionally, architect-driven project creation (chat → ready-to-use project) is blocked because:

- No MCP tool for project creation (`vtf_create_workplan` exists; `vtf_create_project` does not).
- No API endpoint atomically creates project + repo + memberships + initial workplan.
- Bridge/architect sessions do not propagate human identity to vtf, so architect actions are attributed to `vafi-agent` rather than the actual human — a latent identity-layer bug.

This design closes all five gaps in one coherent model.

### Motivating flow

```
User (via vafi-console → architect session):
  "Start a new project 'widgets' on GitLab, namespace viloforge.
   Add me and vafi-agent. Seed a Backlog workplan."

Architect (MCP, one call):
  vtf_bootstrap_project(name="widgets", mode="create",
    repositories=[{name:"main", role:"primary", type:"gitlab", ...}],
    members=[{user_id:"alice", role:"owner"}, ...],
    initial_workplan={name:"Backlog"})

vtf (atomic):
  → calls GitLab API to create git@gitlab.com:viloforge/widgets.git
  → opens DB transaction
  → creates Project, Repository (primary, credential bound), Memberships, Workplan
  → commits transaction
  → emits ProjectBootstrapped audit event
  → returns populated structure

Executor (minutes later):
  polls for todo tasks in the new project → clones primary repo → works
```

---

## 2. Scope

### Goals

- **Multi-repo projects** as the default shape. One primary repo (required) plus zero or more secondaries.
- **First-class repository identity**: type, URL, auth, clone strategy — each repo owns its own values.
- **Provider-pluggable** at the interface level. GitHub, GitLab, Bitbucket, Gitea, self-hosted, and future hosts are added by implementing a driver; no core-code changes.
- **Atomic architect-driven bootstrap** through a single API + MCP surface.
- **Capability-based credential authorization**: holding a credential reference conveys only the exact access the credential permits (target type, URL patterns, operations).
- **Zero-downtime migration** from the current single-`repo_url` model via feature flag and dual-write discipline.
- **Identity propagation fix** so architect actions are attributed to humans, not to the bridge's service account.

### Non-goals (v1)

- User/identity *provisioning* — `members[]` references existing users only; architects do not create teammates.
- k8s secret provisioning — the `github-ssh` secret (or equivalents for other providers) is created out-of-band by cluster-ops.
- CI/CD scaffolding (GitHub Actions, branch protection rules, etc.) on newly-created repos.
- Cross-provider migration of an existing project (GitHub → GitLab move).
- Mirror/replica repositories, bare-git-on-NFS, federated identity.
- Async bootstrap with job polling. Bootstrap is synchronous; P95 target 5s, acceptable ceiling 30s.
- Rate-limit handling beyond "record the provider's response header and expose as a metric".

---

## 3. Conceptual model

Four views, each answering a different question a reader brings to this doc:

- **§3.1 System context (C4 L1)** — where does this system sit in the world?
- **§3.2 Container view (C4 L2)** — what services exist inside, and how do they talk?
- **§3.3 Components (C4 L3, vtf bootstrap path)** — what are the moving parts of the bootstrap flow?
- **§3.4 Bootstrap sequence** — how does a single architect-initiated bootstrap actually unfold?
- **§3.5 Domain entity relationships** — what are the data entities and how are they related?

### 3.1 System context

```mermaid
%%{init: {'theme':'neutral'}}%%
C4Context
    title System Context — Viloforge fleet

    Person(dev, "Developer", "Plans work via architect sessions; reviews fleet runs")
    Person(admin, "Administrator", "Staff user; manages GitHost + RepoCredential records")

    System_Boundary(fleet, "Viloforge fleet") {
        System(vtf, "vtaskforge", "Project/repo/credential data model; REST + MCP; task coordination")
        System(vafi, "vafi", "Autonomous executor + judge; interactive architect sessions via bridge")
    }

    System_Ext(git_hosts, "Git hosts", "GitHub / GitLab / Bitbucket / self-hosted — REST APIs + git SSH")
    SystemDb_Ext(k8s_secrets, "k8s Secrets", "Credential material: SSH keys, tokens, app credentials")

    Rel(dev, vafi, "Chat with architect to bootstrap projects and plan tasks")
    Rel(dev, vtf, "Direct REST / CLI for non-architect workflows")
    Rel(admin, vtf, "Manage credentials and git host records")
    Rel(vtf, git_hosts, "Create/delete repos; validate reachability", "REST")
    Rel(vafi, git_hosts, "Clone, commit, push", "git + SSH/HTTPS")
    Rel(vtf, k8s_secrets, "Resolve secret_ref for provider API auth", "file mount")
    Rel(vafi, k8s_secrets, "Resolve secret_ref for git auth", "file mount")
```

Key context facts the rest of the design depends on:

- **Two systems, one fleet**: vtf owns state; vafi owns execution. Bootstrap is a vtf responsibility (it writes the data model and orchestrates the provider API). Cloning is a vafi responsibility (it runs inside task-executing pods).
- **Git hosts are external**: we never assume a specific one. `github.com` is where Viloforge lives today, but the design treats it as one of N.
- **Credential material lives in k8s Secrets**, not in vtf's database. vtf stores *references* (`secret_ref`); both vtf and vafi mount the underlying Secrets in their respective namespaces.

### 3.2 Container view

```mermaid
%%{init: {'theme':'neutral'}}%%
C4Container
    title Container view — Viloforge fleet

    Person(dev, "Developer")
    Person(admin, "Administrator")

    System_Boundary(fleet, "Viloforge fleet") {
        Container(vtf_api, "vtf API", "Django/DRF + FastMCP", "REST, MCP, auth middleware, bootstrap service")
        ContainerDb(vtf_db, "vtf database", "PostgreSQL", "Projects, Repositories, Credentials, GitHosts, tasks")

        Container(bridge, "vafi bridge", "FastAPI", "Architect session lifecycle; impersonation wiring")
        Container(architect_pod, "vafi architect pod", "k8s pod (pi harness)", "Interactive AI agent; one per user lock")
        Container(executor_pod, "vafi executor pod", "k8s deployment", "Autonomous claim → clone → run gates")
        Container(judge_pod, "vafi judge pod", "k8s deployment", "Autonomous review of completed tasks")
    }

    System_Ext(git_hosts, "Git hosts")
    SystemDb_Ext(k8s_secrets, "k8s Secrets")

    Rel(dev, bridge, "Start architect session", "WebSocket")
    Rel(dev, vtf_api, "Web UI / CLI / REST", "HTTPS")
    Rel(admin, vtf_api, "Credential / host admin", "HTTPS / Django admin")

    Rel(bridge, architect_pod, "Spawn pod; exec pi harness", "k8s API")
    Rel(architect_pod, vtf_api, "MCP calls w/ On-Behalf-Of impersonation", "HTTPS")
    Rel(executor_pod, vtf_api, "Poll, claim, complete", "HTTPS")
    Rel(judge_pod, vtf_api, "Poll reviews, submit verdict", "HTTPS")

    Rel(vtf_api, vtf_db, "Reads + atomic writes", "SQL")
    Rel(vtf_api, git_hosts, "Create/delete repo; validate reach", "REST via httpx")
    Rel(executor_pod, git_hosts, "git clone / push", "SSH / HTTPS")
    Rel(executor_pod, k8s_secrets, "Read SSH key / token", "file mount")
    Rel(vtf_api, k8s_secrets, "Read provider API credentials", "file mount")
```

Why the architect path matters for this design: the architect pod is the only container that calls the new bootstrap surface on the user's behalf. The path `user → bridge → architect pod → vtf API` is what requires identity propagation (§8.1). Executor and judge pods continue to act with the fleet's service token — they don't bootstrap projects.

### 3.3 Components (vtf bootstrap flow)

```mermaid
%%{init: {'theme':'neutral'}}%%
C4Component
    title Components inside vtf API — bootstrap flow

    Container_Boundary(vtf_api, "vtf API") {
        Component(endpoint, "Bootstrap endpoint", "DRF APIView", "POST /v{1,2}/projects/bootstrap/")
        Component(auth_mw, "Auth middleware", "Django middleware", "Token auth + On-Behalf-Of impersonation")
        Component(service, "ProjectBootstrapService", "Service layer", "Orchestrates atomic multi-repo bootstrap")
        Component(rollback, "RollbackStack", "Python class", "LIFO compensation for external side-effects")

        Component(driver_reg, "GitHostDriver registry", "Singleton", "kind → driver class (boot-populated)")
        Component(github_drv, "GitHubDriver", "GitHostDriver impl", "GitHub REST via httpx")
        Component(fake_drv, "FakeHostDriver", "GitHostDriver impl", "Tests only")

        Component(host_svc, "GitHostService", "Service layer", "CRUD + base_url allowlist check")
        Component(cred_svc, "CredentialService", "Service layer", "CRUD + scope + URL-pattern validation")
        Component(repo_svc, "RepositoryService", "Service layer", "CRUD + primary invariant")

        ComponentDb(db, "ORM layer", "Django models", "Project, Repository, RepoCredential, GitHost")
    }

    System_Ext(git_host, "Git host (external)")

    Rel(endpoint, auth_mw, "Gated by")
    Rel(endpoint, service, "Delegates to")
    Rel(service, driver_reg, "Looks up driver by host.kind")
    Rel(driver_reg, github_drv, "Returns")
    Rel(driver_reg, fake_drv, "Returns (tests)")
    Rel(service, host_svc, "Resolves GitHost instance")
    Rel(service, cred_svc, "Validates credential + URL pattern")
    Rel(service, repo_svc, "Creates Repositories atomically")
    Rel(service, rollback, "Pushes undo actions")

    Rel(github_drv, git_host, "Create/delete", "REST")
    Rel(host_svc, db, "CRUD")
    Rel(cred_svc, db, "CRUD")
    Rel(repo_svc, db, "CRUD + invariant check")
```

Read this diagram together with §6 (code abstractions): `GitHostDriver` is the pluggable seam (P5), `RepoCredential`/`GitHost`/`Repository` services enforce invariants per aggregate (§5.6), and `RollbackStack` is the saga mechanism for cross-boundary consistency (§11).

### 3.4 Bootstrap sequence

```mermaid
%%{init: {'theme':'neutral'}}%%
sequenceDiagram
    autonumber
    actor User as Developer
    participant Bridge as vafi bridge
    participant Pod as architect pod
    participant AuthMW as vtf auth middleware
    participant Service as ProjectBootstrapService
    participant Driver as GitHubDriver
    participant GitHost as GitHub API
    participant DB as Postgres

    User->>Bridge: POST /v1/lock (Token: alice)
    Bridge->>AuthMW: validate_token(alice)
    AuthMW-->>Bridge: User(alice, ...)
    Bridge->>Pod: spawn pod<br/>VF_VTF_TOKEN = vafi-agent<br/>VF_ON_BEHALF_OF = alice

    User->>Pod: "Bootstrap project 'widgets' on GitHub"
    Pod->>AuthMW: vtf_bootstrap_project(...)<br/>Authorization: Token vafi-agent<br/>On-Behalf-Of: alice
    AuthMW->>AuthMW: vafi-agent.can_impersonate?<br/>✓ request.user = alice<br/>request.acting_via = vafi-agent
    AuthMW->>Service: bootstrap(spec, actor=alice)

    Service->>Service: validate — scope, patterns, capabilities, invariants
    Service->>Driver: create_repo(spec)
    Driver->>GitHost: POST /user/repos
    GitHost-->>Driver: 201 Created
    Driver-->>Service: DriverRepoResult(external_id, ssh_url, ...)
    Service->>Service: rollback.push(delete_repo)

    Service->>DB: BEGIN
    Service->>DB: INSERT Project, Repository (primary), Memberships, Workplan
    Service->>DB: COMMIT
    Service->>Service: emit ProjectBootstrapped event
    Service-->>AuthMW: Project
    AuthMW-->>Pod: 201 + v2 response envelope
    Pod-->>User: "Created project widgets, repo git@github.com:vilosource/widgets.git"
```

Note the two identity-bearing fields in step 7: `Authorization: Token vafi-agent` (the transport-level credential) and `On-Behalf-Of: alice` (the delegated identity). The middleware in step 8 substitutes the effective `request.user` only if the transport credential has `can_impersonate`. Every downstream audit event records *both* identities — the human who initiated the action and the service account that carried it.

### 3.5 Domain entity relationships

Two views: the persisted data model (§3.5.1) and the code-layer abstractions that operate on it (§3.5.2).

#### 3.5.1 Data model

```mermaid
%%{init: {'theme':'neutral'}}%%
classDiagram
    direction LR

    class User {
        +id: nanoid
        +username: string
        +is_staff: bool
    }

    class ProjectMember {
        +user_id: FK
        +project_id: FK
        +role: owner | member | viewer
    }

    class Project {
        <<Aggregate Root>>
        +id: nanoid
        +name: string
        +status: active | archived
    }

    class Repository {
        +id: nanoid
        +name: string
        +role: primary | secondary
        +type: enum
        +url: string (canonical SSH)
        +default_branch: string
        +clone_options: JSONB
        +external_id: string?
        +clone_ready: bool
    }

    class RepoCredential {
        <<Aggregate Root>>
        +id: nanoid
        +name: string
        +target_type: enum
        +kind: enum
        +secret_ref: string?
        +capabilities: set
        +scope: global | project | staff_only
        +allowed_url_patterns: list~string~
        +enabled: bool
    }

    class GitHost {
        <<Aggregate Root>>
        +id: nanoid
        +name: string
        +kind: enum
        +base_url: string?
        +default_owner: string?
        +capabilities: set
        +enabled: bool
    }

    User "1" -- "0..n" ProjectMember : member_of
    Project "1" *-- "0..n" ProjectMember : has
    Project "1" *-- "1..n" Repository : contains (exactly 1 primary)
    Repository "0..n" ..> "0..1" RepoCredential : auth via
    Repository "0..n" ..> "0..1" GitHost : created via
    GitHost "1" ..> "1" RepoCredential : uses for provider API
    RepoCredential "0..n" ..> "0..1" Project : scope=project only
```

#### 3.5.2 Code abstractions

```mermaid
%%{init: {'theme':'neutral'}}%%
classDiagram
    direction LR

    class GitHostDriver {
        <<abstract, vtf>>
        +kind: ClassVar
        +default_capabilities: ClassVar
        +validate_spec(spec)
        +create_repo(spec)
        +delete_repo(external_id)
        +validate_reachable(credential, url)$
    }

    class GitHubDriver {
        <<vtf, phase 2>>
    }
    class GitLabDriver {
        <<vtf, phase 3>>
    }
    class BitbucketDriver {
        <<vtf, phase 4>>
    }
    class FakeHostDriver {
        <<vtf, tests>>
    }

    class CloneStrategy {
        <<abstract, vafi>>
        +kind: ClassVar
        +prepare_workdir(repo_info, workdir)
    }

    class SshKeyStrategy {
        <<vafi>>
    }
    class HttpsTokenStrategy {
        <<vafi>>
    }
    class PublicStrategy {
        <<vafi>>
    }
    class GitHubAppStrategy {
        <<vafi, future>>
    }

    class ProjectBootstrapService {
        <<vtf>>
        +bootstrap(spec, actor) Project
    }

    class RollbackStack {
        <<vtf>>
        +push(action)
        +push_manual_marker(note)
        +run_best_effort()
    }

    GitHostDriver <|-- GitHubDriver
    GitHostDriver <|-- GitLabDriver
    GitHostDriver <|-- BitbucketDriver
    GitHostDriver <|-- FakeHostDriver

    CloneStrategy <|-- SshKeyStrategy
    CloneStrategy <|-- HttpsTokenStrategy
    CloneStrategy <|-- PublicStrategy
    CloneStrategy <|-- GitHubAppStrategy

    ProjectBootstrapService ..> GitHostDriver : resolves via registry
    ProjectBootstrapService ..> RollbackStack : delegates saga to
```

`GitHostDriver` lives in vtf; `CloneStrategy` lives in vafi. They never share a process. The `kind` enum is the only wire contract between them (§6.4).

Aggregate boundary:
- **`Project`** is the aggregate root. Invariants (exactly-one primary Repository, membership constraints) are enforced on the aggregate.
- **`Repository`**, **`ProjectMember`**, **`Workplan`**, **`Milestone`** are entities within the aggregate.
- **`RepoCredential`** and **`GitHost`** are *separate aggregates* — they have independent lifecycles, are shared across projects, and are administered centrally.

Operations mutate the Project aggregate through `ProjectService` methods (e.g. `ProjectService.add_repository(...)`, `ProjectService.set_primary_repository(...)`), not through direct ORM access to member tables from callers.

---

## 4. Architectural positions (index)

Each position below is asserted, not up for debate. Rationale is cited in the relevant section.

| # | Position | Principle |
|---|----------|-----------|
| P1 | Repository is a first-class model; Project has 1..n Repositories with exactly one primary required | Correct cardinality; domain modeling |
| P2 | Task has no `repo_id` — primary is always cloned, agent decides secondaries from spec | Separation of organizational vs execution concerns (SRP) |
| P3 | RepoCredential is a separate aggregate, referenced by Repository and GitHost via FK | Normalization; single-point rotation |
| P4 | Credential authorization uses scope + URL pattern allowlist from day one | Capability-based security; OCP on policy |
| P5 | GitHostDriver is an ABC; kinds registered at boot, host instances stored in DB | Open/Closed; DIP |
| P6 | CloneStrategy is a vafi-side abstraction; vtf publishes kind enum, vafi validates coverage at startup | Shift-left on integration bugs |
| P7 | Bootstrap emits a single compound `ProjectBootstrapped` event | Audit atom = semantic event |
| P8 | Identity propagation via `On-Behalf-Of` header; architect actions attributed to humans | Identity layer belongs at the auth boundary, not in payloads |
| P9 | Migration uses four-state feature flag; dual-write telemetry gates the cutover | Strangler Fig done properly |
| P10 | Delivery is sliced into coherent shippable increments, not a big-bang release | Deployment safety |
| P11 | Compensating-transaction saga for external rollback; orphan events for unrecoverable cases | Honest trade-off on external consistency |
| P12 | API response includes both `repo_url` (legacy) and `repositories` (new) during overlap; removal is flag-gated | Standard API evolution discipline |

---

## 5. Domain model

### 5.1 `RepoCredential`

A reusable record binding a target host type, an auth material reference, and a capability set. Referenced by Repositories for git-protocol operations and by GitHosts for management-API operations.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | nanoid | no | Primary key |
| `name` | varchar(255) | no | Unique handle (e.g. `github-viloforge-deploy`) |
| `display_name` | varchar(255) | no | Human label for UI |
| `target_type` | enum | no | `github \| gitlab \| bitbucket \| gitea \| raw_git` |
| `kind` | enum | no | `ssh_key \| https_token \| github_app \| public \| gitlab_deploy_token` (extensible) |
| `secret_ref` | varchar(500) | yes | Opaque reference: `k8s-secret:<namespace>/<name>[:<key>]`; null for `kind=public` |
| `metadata` | JSONB | yes | Kind-specific fields (`username` for https, `app_id` for github_app, …) — never contains secret material |
| `capabilities` | set<enum> | no | `{git_auth, provider_api}` — both possible on the same credential |
| `scope` | enum | no | `global \| project \| staff_only` |
| `project_id` | FK Project | yes | Required when `scope=project`, null otherwise; `on_delete=CASCADE` when set |
| `allowed_url_patterns` | JSONB (list of strings) | no | Glob patterns; target URL must match at least one. Empty list = deny-all |
| `enabled` | bool | no | Soft-disable without deletion |
| `created_by` | FK User | yes | Audit |
| `updated_by` | FK User | yes | Audit |
| `created_at`, `updated_at` | timestamp | no | Standard |

Invariants:
- `scope=project` ⇒ `project_id` is not null; `scope∈{global,staff_only}` ⇒ `project_id` is null.
- `kind=public` ⇒ `capabilities = {git_auth}` and `secret_ref` is null.
- `kind=ssh_key` ⇒ `capabilities ⊇ {git_auth}` (SSH keys can't call REST APIs).
- `allowed_url_patterns` is non-empty.
- A credential cannot be deleted while referenced by any `Repository` or `GitHost` (`on_delete=PROTECT` on those FKs). Soft-disable via `enabled=false`.
- When a Project is deleted, its `scope=project` credentials cascade-delete with it (`on_delete=CASCADE`). Rationale: project-scoped credentials have no purpose outside their project; leaving orphans either clutters the credential namespace or risks accidental reuse across unrelated projects.

### 5.2 `GitHost`

A configured connection to a git management API — the authority used when creating new repositories during bootstrap (`mode=create`). Not needed for `mode=import`: imported repos reference a credential directly without a GitHost.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | nanoid | no | Primary key |
| `name` | varchar(255) | no | Unique handle (e.g. `github-main`, `gitlab-internal`) |
| `display_name` | varchar(255) | no | Human label |
| `kind` | enum | no | Same enum as `RepoCredential.target_type` |
| `base_url` | varchar(500) | yes | `https://api.github.com` (null = kind default); non-null for self-hosted |
| `default_owner` | varchar(255) | yes | Fallback for bootstrap when caller omits owner |
| `credential_id` | FK RepoCredential | no | Must have `provider_api` capability and `target_type` matching `kind` |
| `capabilities` | set<enum> | no | Effective capability subset (see §6.2); initially probed at instance creation or set manually |
| `enabled` | bool | no | Soft-disable |
| `created_by`, `updated_by`, timestamps | — | — | Standard |

Invariants:
- `credential.capabilities ⊇ {provider_api}`.
- `credential.target_type == kind`.
- `capabilities ⊆ kind-default-capabilities` (can restrict, not expand).

### 5.3 `Repository`

A first-class git repository within a Project. Exactly one per project has `role=primary`; all others are `secondary`.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | nanoid | no | Primary key |
| `project_id` | FK Project | no | Parent aggregate |
| `name` | varchar(100) | no | Unique within project (e.g. `backend`, `docs`) |
| `role` | enum | no | `primary \| secondary` |
| `type` | enum | no | Host type; same enum as `RepoCredential.target_type` |
| `url` | varchar(500) | no | Canonical SSH URL |
| `https_url` | varchar(500) | yes | Computed for display (optional) |
| `default_branch` | varchar(100) | no | Default "main" |
| `credential_id` | FK RepoCredential | yes | Must have `git_auth` capability; null ⇒ public no-auth |
| `clone_options` | JSONB | no | `{depth?, single_branch?, submodules?, sparse_paths?, ...}`; defaults to `{}` |
| `created_via_host_id` | FK GitHost | yes | Set by `mode=create`; null for `mode=import` |
| `external_id` | varchar(255) | yes | Host-native ID (GitHub numeric repo id, GitLab path) for idempotent lifecycle ops |
| `clone_ready` | bool | no | True when default branch exists with ≥ 1 commit |
| `created_by`, `updated_by`, timestamps | — | — | Standard |

Invariants (enforced by the `Project` aggregate):
- Per project, exactly one Repository with `role=primary`.
- Repository names unique within a project.
- `credential.capabilities ⊇ {git_auth}` if set.
- `credential.target_type == type` (cross-host credential use is rejected).
- `url` matches at least one pattern in `credential.allowed_url_patterns` (if credential set).

Operations on the primary-vs-secondary invariant go through `ProjectService.set_primary_repository(project_id, repo_id)` — atomic demote-and-promote; callers never perform the two field updates separately.

### 5.4 `Project` (updated)

The existing `Project` model retains its columns. Two changes:

| Change | Detail |
|--------|--------|
| `repo_url` | Retained during migration overlap; **deprecated**; removed in final cutover slice. See §13. |
| `default_branch` | Retained during migration overlap; **deprecated**; removed in final cutover slice. |
| (no new column) | Reverse FK `project.repositories` gives access to all Repositories. |

### 5.5 `Task` — unchanged

Task retains only `project_id`. No `repo_id`, no `repos` many-to-many. Rationale (P2):

- The executor always clones the **primary** Repository. Existing tasks continue to work without changes.
- A task spec that requires a secondary repo says so in natural language; the agent reads the spec and clones additional repos on demand via a vafi helper.
- Multi-repo work is a spec concern, not a data-model concern. Pre-declaring which repos a task touches would push execution detail into organizational state and force every multi-repo task into a rigid shape.

### 5.6 Aggregate boundary

The `Project` aggregate encloses Repositories, Memberships, Workplans, Milestones, Tasks. Cross-cutting operations (bootstrap, promote-to-primary, add-repository) are methods on `ProjectService`. Direct ORM manipulation from views/tools is confined to read paths; mutations go through the service.

`RepoCredential` and `GitHost` are **separate aggregates** with their own services:
- `CredentialService` — CRUD, scope validation, capability coercion
- `GitHostService` — CRUD, credential-target-type validation, capability resolution

Cross-aggregate references are by ID only (FKs). This keeps aggregate boundaries consistent with DDD conventions.

---

## 6. Code abstractions

### 6.1 `GitHostDriver` (vtf)

The pluggable implementation of a git host's management API. One class per host kind.

```python
# repo_hosts/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


class Capability(str, Enum):
    CREATE_REPO        = "create_repo"
    DELETE_REPO        = "delete_repo"
    AUTO_INIT          = "auto_init"
    DEPLOY_KEYS        = "deploy_keys"
    WEBHOOKS           = "webhooks"
    BRANCH_PROTECTION  = "branch_protection"
    VALIDATE_REACH     = "validate_reachable"
    RENAME             = "rename"
    TRANSFER           = "transfer"


@dataclass(frozen=True)
class RepoCreateSpec:
    name: str
    owner: str
    description: str
    private: bool
    default_branch: str
    auto_init_readme: bool
    extra: dict | None   # kind-specific, validated by the driver

@dataclass(frozen=True)
class DriverRepoResult:
    ssh_url: str
    https_url: str
    default_branch: str
    external_id: str
    clone_ready: bool


class GitHostDriver(ABC):
    kind: ClassVar[str]
    default_capabilities: ClassVar[frozenset[Capability]]

    def __init__(self, host: GitHost, credential: RepoCredential): ...

    @abstractmethod
    def validate_spec(self, spec: RepoCreateSpec) -> None:
        """Raise ValidationError (DRF) if invalid for this kind + this host's config."""

    @abstractmethod
    def create_repo(self, spec: RepoCreateSpec) -> DriverRepoResult: ...

    @abstractmethod
    def delete_repo(self, external_id: str) -> None: ...

    @classmethod
    @abstractmethod
    def validate_reachable(cls, credential: RepoCredential, url: str) -> bool:
        """Reachability check — usable in import mode where no GitHost exists.
        Takes the credential directly; no host instance required."""
```

`validate_reachable` is a classmethod because import mode has no `GitHost` to bind a driver instance to. The credential alone is sufficient to attempt a network check.

Driver registration at boot (one line per kind):

```python
# repo_hosts/apps.py
class RepoHostsConfig(AppConfig):
    name = "repo_hosts"
    def ready(self):
        from repo_hosts.registry import driver_registry
        from repo_hosts.github.driver import GitHubDriver
        driver_registry.register(GitHubDriver)
        # Later: driver_registry.register(GitLabDriver), etc.
```

Driver instantiation is *per-operation*: `driver = driver_registry.get(host.kind)(host, host.credential)`. Drivers are stateless beyond the host + credential they were created for; no shared mutable state across requests.

### 6.2 Capability model

Capabilities serve two purposes:

1. **Driver-class capabilities** (`GitHubDriver.default_capabilities`) — what this host kind is *theoretically* able to do.
2. **Host-instance capabilities** (`GitHost.capabilities`) — the *effective* subset given this instance's credentials. A host bound to a read-only token has narrower capabilities than the class allows.

Effective capabilities are either declared at host-create time (admin knows the token scope) or probed by calling a driver method that introspects scope. For v1: declared at creation; probing is future work.

Callers check capability before invoking optional methods:

```python
if Capability.DELETE_REPO not in host.capabilities:
    raise ProviderCapabilityError(host, Capability.DELETE_REPO)
driver.delete_repo(external_id)
```

### 6.3 `CloneStrategy` (vafi)

The vafi-side sibling abstraction. Takes Repository data (credential kind + secret_ref + clone_options) and materializes a checkout into a workdir.

**The `RepoInfo` DTO** — the contract between vtf (via the clone-info endpoint, §9.5) and vafi's strategy layer. This is the minimum data vafi needs to clone; it intentionally does not include the secret material (which lives in a k8s Secret that vafi mounts locally).

```python
@dataclass(frozen=True)
class RepoInfo:
    id: str                   # Repository.id
    url: str                  # canonical SSH URL
    default_branch: str
    credential_kind: str      # ssh_key | https_token | github_app | public
    secret_ref: str | None    # k8s-secret:<ns>/<name>[:<key>], or None for public
    metadata: dict            # kind-specific, non-secret (username, app_id, etc.)
    clone_options: dict       # depth, submodules, sparse_paths, single_branch, ...
```

vtf serializes this shape exactly; vafi deserializes and dispatches.

```python
# vafi/src/controller/clone_strategies/base.py
class CloneStrategy(ABC):
    kind: ClassVar[str]  # matches RepoCredential.kind

    @abstractmethod
    def prepare_workdir(self, repo_info: RepoInfo, workdir: Path) -> None:
        """Clone the repo into workdir using the strategy's auth + git flags."""

class SshKeyStrategy(CloneStrategy):
    kind = "ssh_key"
    # Reads secret_ref → file path; configures GIT_SSH_COMMAND; git clone git@...

class HttpsTokenStrategy(CloneStrategy):
    kind = "https_token"
    # Reads secret_ref → token; git clone https://x-access-token:$TOK@...

class PublicStrategy(CloneStrategy):
    kind = "public"
    # git clone https://... with no credential

class GitHubAppStrategy(CloneStrategy):
    kind = "github_app"
    # Mints a short-lived installation token per clone
```

Dispatch is on `repo.credential.kind`. Registry mirrors vtf's:

```python
strategy_registry.register(SshKeyStrategy())
strategy_registry.register(HttpsTokenStrategy())
strategy_registry.register(PublicStrategy())
```

### 6.4 Kind contract between vtf and vafi

vtf is the source of truth for the enumeration of `RepoCredential.kind` values. vafi must implement a `CloneStrategy` for every kind vtf can accept.

**Startup-time validation (vafi):**

```python
# vafi boot
published_kinds = set(httpx.get(f"{VTF_API_URL}/v1/credential-kinds/").json()["kinds"])
implemented_kinds = set(strategy_registry.keys())
missing = published_kinds - implemented_kinds
if missing:
    logger.error(f"Missing clone strategies: {missing}. Refusing to start.")
    sys.exit(1)
```

This shifts integration bugs from task-time (silent hang during a real task) to boot-time (pod fails to start, alerting is immediate).

---

## 7. Registration & resolution

### 7.1 Driver registry (kinds → classes)

Compiled-in. Populated at Django `AppConfig.ready()`. Keyed by `GitHostDriver.kind`. Immutable after boot. Tests inject a `FakeHostDriver` by registering under a reserved kind (`fake`).

### 7.2 GitHost resolver (DB-backed)

```python
class GitHostResolver:
    def resolve(self, name: str) -> GitHostDriver:
        host = GitHost.objects.get(name=name, enabled=True)
        driver_class = driver_registry.get(host.kind)
        return driver_class(host=host, credential=host.credential)
```

No caching in v1. Each bootstrap call performs the lookup fresh. When caching matters, add with a short TTL and a cache-invalidation trigger on host/credential update.

### 7.3 Credential resolution

When a Repository is used (clone time, on vafi side):

```python
# vafi
credential = fetch_credential_from_vtf(repo.credential_id)
strategy = strategy_registry.get(credential.kind)
strategy.prepare_workdir(repo_info, workdir)
```

`fetch_credential_from_vtf` returns a DTO containing `kind`, `secret_ref`, `metadata` — **never the secret material**. vafi resolves `secret_ref` locally against its own k8s Secret mount. See §8.5.

---

## 8. Authorization & security

### 8.1 Actor identity — On-Behalf-Of impersonation (P8)

**Problem (verified 2026-04-18, `bridge/app.py:402`, `pi_session.py:60`):** the bridge currently spawns architect pods with `VF_VTF_TOKEN = VTF_API_TOKEN` — the bridge's own `vafi-agent` service token. Every architect-originated MCP call is attributed to `vafi-agent`, not to the human who initiated the session. Bootstrap (and reviews, task creates, notes) inherit this bug.

**Solution:** OAuth2-style "on-behalf-of" delegation.

**vtf-side middleware (new, in `core/auth.py`):**

```python
class OnBehalfOfMiddleware:
    """If the request carries both a service token AND an On-Behalf-Of header,
    AND the service token user has `can_impersonate`, substitute the request
    user while recording both identities for audit."""
    def __call__(self, request):
        authed_user = request.user  # set by TokenAuthMiddleware
        target_username = request.headers.get("On-Behalf-Of")
        if target_username and authed_user.has_perm("impersonation.can_impersonate"):
            request.acting_via = authed_user
            request.user = User.objects.get(username=target_username)
        return self.get_response(request)
```

**Bridge-side (minor change in `bridge/app.py`):**

```python
env_vars["VF_ON_BEHALF_OF"] = user["username"]  # human from require_auth
```

**pi-mcp-adapter / MCP client (in the pod):**

When `VF_ON_BEHALF_OF` is set, adds the header to every MCP HTTP request.

**Audit:** every authenticated write records *both* identities: `TaskEvent.actor = <human>`, `TaskEvent.acting_via = <vafi-agent>`. Audit consumers see who asked and through what channel.

**Granting `can_impersonate`:** Django permissions are `ContentType`-linked, so a global capability needs a carrier. A dedicated `Impersonation` Django model (schema-only, no columns beyond `id`) hosts the permission; `vafi-agent` gets the grant via data-migration. Alternative (rejected): BooleanField on User — breaks the Django idiom and doesn't appear in the admin's permission UI. Future per-bridge service accounts receive the grant the same way.

Slice 0 in the delivery plan (§16) implements this. **Bootstrap is blocked on Slice 0.** Without impersonation, every bootstrapped project would have `vafi-agent` as owner — wrong.

### 8.2 Credential scope (P4)

Three scope values, all present in the enum from day one:

| Scope | Visibility | Use |
|-------|-----------|-----|
| `global` | Any authenticated user can reference | Org-wide shared credentials (e.g. the shared github-ssh deploy key) |
| `project` | Only members of the credential's `project_id` can reference | Customer-specific or per-project credentials |
| `staff_only` | Only Django staff users can reference when creating/updating repositories | Admin escape hatch for privileged operations |

The credential-resolution service enforces scope on every reference, including during bootstrap, repository CRUD, and any future operation. The UI in v1 exposes only `global` and `staff_only` when creating credentials; `project` scope is settings-gated (`ENABLE_PROJECT_SCOPED_CREDENTIALS=true`) and rolled out when the multi-tenant use case materializes. The model and resolution path support all three from the start.

### 8.3 URL pattern allowlists (P4)

Every credential carries `allowed_url_patterns`, non-empty, glob-style. When a Repository is created or its URL is updated, the URL must match at least one of the credential's patterns. Otherwise the operation is rejected.

**URL canonicalization is performed before matching.** All URLs are normalized to SCP-like SSH form (`git@<host>:<path>.git`) at Repository write time. HTTPS URLs (`https://host/path[.git]`) are converted; `ssh://git@host/path` (URI form) is converted to SCP form. Patterns are authored and stored in the same canonical form. This closes the "same repo, two URL shapes" bypass where a pattern `git@github.com:vilosource/*` wouldn't match `https://github.com/vilosource/foo` despite both denoting the same resource.

**Pattern matching library**: `fnmatch.fnmatchcase` (Python stdlib, Unix-shell glob semantics, case-sensitive). `*` matches any sequence except `/` is not special in fnmatch — this is acceptable because we match full canonical URLs, and the `git@host:` prefix forces the boundary. Regex is deliberately avoided — ReDoS risk is real and admins shouldn't be crafting regex for security boundaries.

Example:

```
RepoCredential(name="github-viloforge-deploy")
  target_type=github
  scope=global
  allowed_url_patterns=["git@github.com:vilosource/*"]
```

Matches (after canonicalization):
- `git@github.com:vilosource/widgets.git` ✓
- `https://github.com/vilosource/widgets` → normalized → `git@github.com:vilosource/widgets.git` ✓

Rejects:
- `git@github.com:someone-else/private-repo.git` ✗

The defense is at credential-use time, centrally enforced, and doesn't depend on every caller remembering to check.

### 8.4 What is never returned in API responses

- `RepoCredential.secret_ref` — leaks the storage location; attacker could then target the Secret directly.
- `RepoCredential.metadata` if it would imply details of the secret (e.g. `ssh_host` could, but doesn't — SSH hostnames are public). Conservative rule: metadata is allowed if documented safe for each field; default is omit.
- `GitHost.credential_id` is returned (non-secret), but its credential's material is not.

API responses include `name`, `display_name`, `target_type`, `kind`, `capabilities`, `scope`, `allowed_url_patterns`, `enabled` — never anything that maps to storage-level access.

### 8.5 Secret material lifecycle (v1 approach)

`secret_ref` uses the scheme `k8s-secret:<namespace>/<name>[:<key>]`. Both vtf and vafi pods mount the referenced Secret in their respective namespaces. Key material never passes through the vtf HTTP surface.

**Sync mechanism.** A Secret referenced by `secret_ref` must exist with matching content in both the vtf and vafi namespaces. v1 supports two sync modes, selectable via ops:

- **ExternalSecrets Operator (preferred)**: a single source-of-truth `ExternalSecret` resource in each namespace points at the same upstream (Vault / AWS Secrets Manager / 1Password Connect). Rotation happens once upstream; both namespaces pick up changes without redeploy. Requires ESO installed in the cluster.
- **Manual sync with checklist (bootstrap mode)**: a documented runbook (`docs/ops/credential-sync.md`, to be written in Slice 2) lists every Secret and its two namespace locations; operators update both when rotating. Acceptable short-term; error-prone long-term.

vtf's credential-write path performs a startup-time sanity probe: on each pod startup, for every enabled credential, vtf attempts to read the referenced Secret in its own namespace. Failures are logged but non-fatal (vafi reads independently). vafi performs the same check on its side. Structured metric `credential_secret_resolution_errors` exposes the status per credential.

**Future hardening (out of scope v1):** replace `secret_ref` with a vtf-managed encrypted store, exposing `GET /v1/credentials/<id>/material/` as an authenticated least-privilege API that vafi calls per-task. Gives audit, rotation, and revocation without restart. Design preserves compatibility — `kind` and `capabilities` don't change.

### 8.6 Threat summary

| Threat | Defense |
|--------|---------|
| Compromised member token references a global credential to clone arbitrary URL | `allowed_url_patterns` match required (§8.3, with URL canonicalization) |
| Compromised member token escalates by creating a `staff_only` credential | Scope CRUD restricted to staff |
| Malicious task spec points the agent at a secondary repo with sensitive contents | Secondary repos also go through Repository model + credential check; agent's on-demand clone helper enforces same checks as primary |
| Compromised vafi pod exfiltrates all credentials | Today: k8s Secret has everything mounted. Future mitigation (8.5): per-task material fetch |
| API response accidentally leaks secret_ref | Serializer explicitly omits; contract test asserts it |
| Architect action attributed to wrong user | On-Behalf-Of impersonation + dual-actor audit |
| Staff user points `GitHost.base_url` at attacker-controlled host to exfiltrate bot token | `base_url` validated against per-kind allowlist defined in settings (e.g. `VTF_GITHOST_BASE_URL_ALLOWLIST = {"github": ["https://api.github.com", "https://ghes.viloforge.com/api/v3"], "gitlab": ["https://gitlab.com", "https://gitlab.viloforge.com"]}`). Edits to base_url require staff + pass allowlist check; changes emit an audit event. |
| Feature-flag downgrade (new → dual → off) orphaning Repository data | `off` state is dormant-read only; Repository rows remain; downgrade is safe |

---

## 9. API surface

### 9.1 Bootstrap endpoint

```
POST /v1/projects/bootstrap/     — returns v1-shape envelope
POST /v2/projects/bootstrap/     — returns v2-shape envelope (embedded refs, permissions)
```

Both paths are supported per vtf's existing dual-versioning convention. `VersionedSerializerMixin` selects the response serializer from URL prefix. Request-body shape is identical across versions.

**Idempotency:** not implemented in v1. A client retrying after a network timeout against `mode: "create"` can produce partial state — the first call may have succeeded at the provider but the response was lost. **Callers must inspect state (via provider introspection or via `GET /v1/projects/?repo_url=<url>`) before retrying.** An `Idempotency-Key` header is deferred to a future hardening pass; the doc will add it alongside telemetry for duplicate-bootstrap attempts once real usage data exists.

**Create mode (single-repo):**

```json
{
  "name": "widgets-api",
  "description": "Widget REST service",
  "members": [
    {"user_id": "vafi-agent", "role": "member"},
    {"user_id": "alice",      "role": "owner"}
  ],
  "repositories": [
    {
      "name": "main",
      "role": "primary",
      "mode": "create",
      "type": "github",
      "host": "github-main",
      "credential": "github-viloforge-deploy",
      "spec": {
        "owner": "vilosource",
        "repo_name": "widgets-api",
        "private": true,
        "default_branch": "main",
        "auto_init_readme": true,
        "description": "Widget REST service",
        "extra": {}
      }
    }
  ],
  "initial_workplan": {"name": "Backlog", "description": ""}
}
```

**Create mode (multi-repo) — mixed providers, import + create:**

```json
{
  "name": "widgets-platform",
  "members": [...],
  "repositories": [
    {
      "name": "backend", "role": "primary", "mode": "create",
      "type": "github", "host": "github-main", "credential": "github-viloforge-deploy",
      "spec": {"owner": "vilosource", "repo_name": "widgets-backend", ...}
    },
    {
      "name": "frontend", "role": "secondary", "mode": "create",
      "type": "gitlab", "host": "gitlab-internal", "credential": "gitlab-internal-deploy",
      "spec": {"owner": "widgets", "repo_name": "widgets-frontend", ...}
    },
    {
      "name": "docs", "role": "secondary", "mode": "import",
      "type": "github", "credential": "github-viloforge-deploy",
      "spec": {"url": "git@github.com:vilosource/widgets-docs.git", "default_branch": "main"}
    }
  ]
}
```

**Response (201 Created):**

```json
{
  "project": { /* v2 Project shape, includes `repositories` expansion */ },
  "repositories": [ /* array of v2 Repository shapes */ ],
  "members": [ /* membership records */ ],
  "workplan": { /* v2 Workplan shape, if initial_workplan given */ },
  "event_id": "evt_..."
}
```

**Errors:**

| Status | Code | Meaning |
|--------|------|---------|
| 400 | `VALIDATION_ERROR` | Spec/payload structurally invalid |
| 400 | `UNKNOWN_USER` | `members[*].user_id` not found |
| 400 | `UNKNOWN_HOST` | `repositories[*].host` not found or disabled |
| 400 | `UNKNOWN_CREDENTIAL` | `repositories[*].credential` not found or disabled |
| 400 | `CREDENTIAL_CAPABILITY_MISMATCH` | Credential lacks `git_auth` for a repo, or host credential lacks `provider_api` |
| 400 | `CREDENTIAL_TARGET_MISMATCH` | Credential's `target_type` ≠ repo `type` |
| 400 | `CREDENTIAL_URL_PATTERN_MISMATCH` | Target URL not in credential's `allowed_url_patterns` |
| 400 | `CREDENTIAL_SCOPE_DENIED` | Credential scope forbids caller from referencing it |
| 400 | `INVALID_REPOSITORY_COMPOSITION` | Not exactly one primary; duplicate names within a project |
| 400 | `HOST_MISSING_CAPABILITY` | `mode=create` but host lacks `CREATE_REPO` |
| 401 | `AUTHENTICATION_REQUIRED` | No authenticated caller |
| 403 | `IMPERSONATION_DENIED` | `On-Behalf-Of` used but caller lacks `can_impersonate` |
| 409 | `REPO_ALREADY_EXISTS` | Provider rejected create because (owner, repo_name) is taken |
| 409 | `PROJECT_URL_TAKEN` | vtf already has a project with that repo URL (import mode) |
| 422 | `PROVIDER_ERROR` | Driver returned an unrecognized error; orphan-cleanup attempted |
| 502 | `PROVIDER_UNREACHABLE` | Network/timeout failure talking to provider |

### 9.2 Repository CRUD

```
POST   /v1/projects/{project_id}/repositories/   — add secondary (create or import)
GET    /v1/projects/{project_id}/repositories/   — list
GET    /v1/repositories/{id}/                    — detail
PATCH  /v1/repositories/{id}/                    — update name, clone_options, credential (not type/url)
DELETE /v1/repositories/{id}/                    — delete (not allowed if role=primary unless project is being deleted)
POST   /v1/repositories/{id}/promote/            — atomic promote-to-primary (demotes existing primary)
```

Permission: member of the project. Credential references subject to §8.2–8.3.

### 9.3 RepoCredential CRUD (staff)

```
POST   /v1/credentials/
GET    /v1/credentials/    — authenticated users see credentials in their visibility scope (see §8.2)
GET    /v1/credentials/{id}/
PATCH  /v1/credentials/{id}/    — rotate secret_ref, toggle enabled, adjust patterns (never change target_type)
DELETE /v1/credentials/{id}/    — PROTECTED if referenced; force soft-disable instead
```

Create/update: staff only. `secret_ref` never returned in responses.

### 9.4 GitHost CRUD (staff)

```
POST   /v1/hosts/
GET    /v1/hosts/
GET    /v1/hosts/{id}/
PATCH  /v1/hosts/{id}/
DELETE /v1/hosts/{id}/    — PROTECTED if referenced by Repository.created_via_host_id
```

### 9.5 Discovery endpoints

```
GET /v1/hosts/              → list GitHost instances (authenticated users)
GET /v1/credentials/        → list credentials in caller's scope
GET /v1/host-kinds/         → list compiled-in driver kinds (staff; for admin UI)
GET /v1/credential-kinds/   → list supported credential kinds (authenticated; vafi polls at startup)
GET /v1/repository-model/   → current feature-flag state + equivalence-probe result (§13.5)
```

### 9.6 Clone-info endpoint (vafi-facing)

vafi needs to fetch exactly what it needs to clone — no more. A dedicated endpoint serves this, distinct from the staff-level credential CRUD:

```
GET /v1/repositories/{id}/clone-info/
```

**Response (200):**

```json
{
  "id": "repo_...",
  "url": "git@github.com:vilosource/widgets.git",
  "default_branch": "main",
  "credential_kind": "ssh_key",
  "secret_ref": "k8s-secret:vafi-secrets/github-ssh",
  "metadata": {},
  "clone_options": {}
}
```

**Permissions:** the caller's token must correspond to a user who is a member of the Repository's Project. `vafi-agent` is added to every project that uses the fleet (Slice 1c enforces the invariant). The response deliberately omits credential name, display name, scope, allowed patterns, capabilities — vafi doesn't need those and shouldn't have visibility into the authorization surface.

This endpoint is the vtf → vafi boundary. Adding fields here requires a coordinated vtf+vafi release.

### 9.7 API versioning & evolution (P12)

During the migration overlap, the v2 `Project` response includes both `repo_url` (legacy, computed from the primary Repository) **and** `repositories` (new, full list):

```json
{
  "id": "...", "name": "...",
  "repo_url": "git@github.com:vilosource/widgets.git",     // legacy, computed
  "repositories": [
    { "id": "...", "name": "main", "role": "primary", ... },
    ...
  ]
}
```

Old clients read `repo_url`; new clients read `repositories`. `repo_url` removal is gated on the `removed` feature-flag state (§13.1) and is a deprecation announced one release cycle ahead; the v2 response shape does not introduce a breaking change.

---

### 9.8 Repository cardinality limits

A soft limit of **20 Repositories per Project** is enforced at the `ProjectService` layer. Exceeding it returns `REPOSITORY_LIMIT_EXCEEDED` (HTTP 400). The limit is a configuration setting (`VTF_MAX_REPOSITORIES_PER_PROJECT=20`) so it can be raised for specific deployments without a code change.

Rationale: bootstrap is synchronous and makes one provider call per `mode=create` repo. A project with 50 repos takes ≥ 50 seconds; beyond that we're into async-bootstrap territory (a v2 concern). 20 is comfortable for real-world multi-repo projects (backend + frontend + mobile + docs + infra + ~15 microservices) without inviting runaway calls.

No hard DB limit — the check is at service layer so ops can temporarily override for a known-good bulk-import scenario.

---

## 10. MCP tools

Tools follow Phase 4c conventions (`docs/design/phase4c-mcp-redesign-DESIGN.md`): decorator-based error handling, v2 serializer-backed responses, project-access guards.

| Tool | Purpose |
|------|---------|
| `vtf_bootstrap_project` | The single-call bootstrap entrypoint for architects |
| `vtf_list_hosts` | Enumerate available GitHost instances (name, kind, display name, capabilities) |
| `vtf_list_credentials` | Enumerate credentials visible to the caller (name, target_type, capabilities) |
| `vtf_add_repository` | Add a secondary repo to an existing project (create or import) |
| `vtf_list_repositories` | List repos in a project |
| `vtf_set_primary_repository` | Promote a secondary to primary |
| `vtf_delete_repository` | Remove a secondary |

**Explicitly not exposed via MCP**: credential creation, host creation. These are staff operations; architects reference existing objects by name but cannot mint new credentials.

`vtf_bootstrap_project` signature mirrors the endpoint's JSON shape, flattened to MCP's string-only parameter convention with JSON-encoded sub-objects where needed (e.g. `repositories` is a JSON-array string).

**Error shape** follows the existing MCP convention (`mcp_server/responses.py::error_response`): `{"success": false, "data": {}, "message": "<actionable text>", "available_actions": [...]}`. Every API error code from §9.1 maps to a `message` string with the code embedded (e.g. `"CREDENTIAL_URL_PATTERN_MISMATCH: URL 'git@github.com:foo/bar' does not match any pattern on credential 'github-viloforge-deploy'"`). Structured error details go into `data.error_code` for programmatic handling; humans read `message`.

---

## 11. Failure semantics

### 11.1 Compensating-transaction saga (P11)

Bootstrap crosses two consistency boundaries: the driver's external API and the vtf database. True ACID is impossible. The chosen model is compensating transactions:

```python
def bootstrap_create(spec, actor):
    rollback = RollbackStack()
    try:
        for r in spec.create_repositories:
            host = resolve_host(r.host)
            driver = driver_registry.get(host.kind)(host, host.credential)
            driver.validate_spec(r.repo_spec)
            result = driver.create_repo(r.repo_spec)
            if Capability.DELETE_REPO in host.capabilities:
                rollback.push(lambda: driver.delete_repo(result.external_id))
            else:
                rollback.push_manual_marker(f"orphan {host.kind}:{result.external_id}")
            r._created_result = result

        with transaction.atomic():
            project = create_project_rows(spec, actor)
            for r in spec.repositories:
                create_repository_row(project, r)
            add_memberships(project, spec.members)
            if spec.initial_workplan:
                create_workplan(project, spec.initial_workplan)
            emit_event("project.bootstrapped", ...)
            return project

    except Exception:
        rollback.run_best_effort()
        raise
```

### 11.2 RollbackStack

```python
class RollbackStack:
    """LIFO cleanup of external side effects. Failures during rollback
    emit OrphanResourceEvent rather than shadowing the original exception."""

    def push(self, action: Callable[[], None]) -> None: ...
    def push_manual_marker(self, note: str) -> None: ...
    def run_best_effort(self) -> None:
        for action in reversed(self._actions):
            try:
                action()
            except Exception as e:
                self._emit_orphan_event(action, e)
```

### 11.3 Orphan events

When external rollback fails (or a driver lacks `DELETE_REPO`), an `OrphanResourceEvent` is written with:
- `host_kind`, `host_name`, `external_id`, `url`
- `bootstrap_request_id` for correlation
- `reason` (exception text or "capability-missing")

Operators have a structured log query to find and hand-clean. Not emitted to unstructured logs.

---

## 12. vafi-side impact

### 12.1 Executor refactor

Current: `vafi/src/controller/controller.py::_poll_and_execute` calls `self.work_source.get_repo_info(task.project_id)` and treats the returned single repo as authoritative.

New: `get_repo_info(project_id)` returns the primary Repository's data (backward compatible with current callers). A new `list_repos(project_id)` returns all Repositories in the project. `get_repo_info` response includes `credential_id`, `credential_kind`, `secret_ref`, `clone_options`.

During the migration (feature flag in `dual` or `new` state), `get_repo_info` reads from Repository; during `off` it reads from `Project.repo_url`. The executor's call site is unchanged.

### 12.2 CloneStrategy dispatch

`_invoker._ensure_repo_cloned` is refactored:

```python
def _ensure_repo_cloned(self, repo_info, workdir):
    strategy = strategy_registry.get(repo_info.credential_kind)
    strategy.prepare_workdir(repo_info, workdir)
```

`SshKeyStrategy` implements today's behavior (using `~/.ssh/id_ed25519` via the init container + github-ssh secret). Other strategies land as new kinds need them.

### 12.3 Secondary-repo on-demand clones

Agents may call additional repos into the workdir via a **new vafi helper** (`/opt/vf-agent/bin/vfctl clone <repo-name>`) introduced as part of Slice 1c. This helper does not exist in the current codebase; it's a deliverable of this initiative.

Behavior:
1. Reads the current task's `project_id` from env (`VF_TASK_PROJECT_ID`, set by the controller at harness invocation time).
2. Calls vtf `GET /v1/repositories/?project={id}&name={name}` (using the pod's `VF_VTF_TOKEN`).
3. Calls `GET /v1/repositories/{id}/clone-info/` to get the `RepoInfo` DTO (§6.3).
4. Dispatches via `CloneStrategy` registry, the same path the executor uses for the primary repo.
5. Clones into `workdir/<repo-name>/`.

The `<repo-name>` argument is resolved within the current project's scope — no cross-project ambiguity. Agents without a project context (edge case) see a clear error.

The helper is documented in the executor methodology (`methodologies/executor.md`) so agents know how to invoke it from spec-described multi-repo work.

---

## 13. Migration & rollout

### 13.1 Feature flag state machine (P9)

Single flag, shared by vtf and vafi: `VTF_REPOSITORY_MODEL`. Implemented as a **Django setting read from env var at process start** — not a hot-toggleable DB flag. Rationale: a mid-request flip during `dual → new` could cause torn reads (one transaction reads Repository, a concurrent one reads `repo_url`); settings-based means the entire pod observes one consistent state for its lifetime. The operational cost is a redeploy per transition — acceptable for a migration expected to last weeks, not hours.

Deploy-time values:
- `VTF_REPOSITORY_MODEL=off` — initial deploy of Slice 1a
- `VTF_REPOSITORY_MODEL=dual` — after Slice 1a data migration passes equivalence tests
- `VTF_REPOSITORY_MODEL=new` — after vafi fleet is fully on Repository-aware code
- `VTF_REPOSITORY_MODEL=removed` — after stop criteria (§13.3) are met

**Kind-enum evolution ordering.** When adding a new credential kind (e.g. `gitea_ssh_key`), the rollout order is strict:

1. Ship vafi with the new `CloneStrategy` registered. The strategy is dormant until a credential of that kind exists.
2. Ship vtf with the new kind added to `/v1/credential-kinds/` and the `RepoCredential.kind` enum.
3. Create credentials of the new kind (admin action).

Reversing steps 1 and 2 would cause every vafi pod to fail startup validation (§6.4) — an outage for the entire fleet. The rollout order is included in the release checklist for any PR that adds a kind.

| State | vtf | vafi |
|-------|-----|------|
| `off` | Legacy `repo_url` only. Repository models exist but are dormant. | Reads `repo_url` from Project serializer. |
| `dual` | Dual-write: creates Repository rows when repo_url is written; reads primary as source-of-truth but returns both fields. | Prefers Repository from serializer; falls back to `repo_url` if absent. |
| `new` | Repository is source of truth. `repo_url` still returned (computed from primary) for backward compat. | Reads Repository only; no fallback path. |
| `removed` | `repo_url` column and field dropped. | — |

Transitions happen in this order with verification gates between each:

1. Deploy vtf with `off`. Data migration runs; Repository rows created for every Project; dormant.
2. Flip vtf to `dual`. Monitor dual-write correctness via contract tests (§13.5) for at least 48h.
3. Roll vafi with updated image (Repository-aware). Still reads `repo_url` by default.
4. Flip vafi to `dual`. Verify executor tasks still complete. Monitor for any `repo_url`-only callers.
5. Flip both to `new`. Monitor stop criteria (§13.3) for at least 14 days.
6. Flip to `removed`. Drop column in a follow-up migration.

### 13.2 Dual-write strategy

In `dual` state:
- Writes to `Project.repo_url` also create/update the Project's primary Repository (via post_save signal).
- Writes to the primary Repository also update `Project.repo_url` (via post_save signal).
- Reads prefer Repository; fall back to `repo_url` if none exists (defense against a race).

**Signal loop prevention.** Each sync direction guards against re-trigger via a thread-local flag:

```python
_SYNCING = threading.local()

@receiver(post_save, sender=Project)
def project_to_repo_sync(sender, instance, update_fields, **kwargs):
    if getattr(_SYNCING, "active", False):
        return  # we're inside a syncing operation, skip
    if update_fields and "repo_url" not in update_fields:
        return  # unrelated field update
    _SYNCING.active = True
    try:
        _update_primary_repository(instance)
    finally:
        _SYNCING.active = False
```

The reverse direction uses the same `_SYNCING` flag. This is belt-and-suspenders — both the `update_fields` check and the thread-local guard must fail for a loop to occur.

Signals emit `legacy_write` telemetry counters so we can see when legacy writes stop occurring in the wild.

### 13.3 Cutover stop criteria

The transition from `new` to `removed` requires all four observable conditions, held green for 14 days:

1. **Zero reads** of `Project.repo_url`. Instrument via query-log sampling or a `@TrackedField` wrapper that counts accesses.
2. **Zero writes** to `Project.repo_url`. Any writes indicate a missed caller.
3. **All deployed vafi pods** on an image tag that contains the Repository-aware controller code. Verified via `kubectl get pods -l app.kubernetes.io/component=executor* -o jsonpath=... | grep -v <new-tag>` returning empty.
4. **All known external clients** (CLI, any third-party integrations) confirmed updated.

If any criterion regresses, the cutover is paused and the responsible caller is identified. No time-pressure override — the criteria are the gate.

### 13.4 Data migration for existing Projects

A one-shot data migration (`projects/migrations/00XX_seed_repository_rows.py`) runs during deploy of `off` state:

```python
def seed_repositories(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Repository = apps.get_model("repos", "Repository")
    RepoCredential = apps.get_model("credentials", "RepoCredential")

    # Create a legacy credential for the existing github-ssh implicit key
    legacy_cred, _ = RepoCredential.objects.get_or_create(
        name="legacy-github-ssh",
        defaults={
            "target_type": "github",
            "kind": "ssh_key",
            "secret_ref": "k8s-secret:vafi-secrets/github-ssh",
            "capabilities": ["git_auth"],
            "scope": "global",
            "allowed_url_patterns": ["git@github.com:*"],
        },
    )

    for project in Project.objects.all():
        if not project.repo_url:
            continue  # Empty projects stay empty
        if project.repositories.exists():
            continue  # Already migrated
        inferred_type = _infer_type_from_url(project.repo_url)
        Repository.objects.create(
            project=project,
            name="main",
            role="primary",
            type=inferred_type,
            url=_canonicalize_url(project.repo_url),
            default_branch=project.default_branch or "main",
            credential_id=legacy_cred.id if inferred_type == "github" else None,
            clone_options={},
        )


def _infer_type_from_url(url: str) -> str:
    """Map a repo URL to a RepoCredential.target_type value.

    Matching is strict: unknown hosts raise rather than silently mapping
    to `raw_git`, because a wrong type disables provider operations
    (create/delete) for that project and is hard to notice after the fact.
    """
    if re.search(r"(?:@|//)github\.com[:/]", url):
        return "github"
    if re.search(r"(?:@|//)gitlab\.com[:/]", url):
        return "gitlab"
    if re.search(r"(?:@|//)bitbucket\.org[:/]", url):
        return "bitbucket"
    # Self-hosted patterns: honor env-var allowlist
    for kind, hosts in settings.VTF_SELFHOSTED_URL_PATTERNS.items():
        if any(re.search(p, url) for p in hosts):
            return kind
    raise MigrationError(
        f"Cannot infer type from url {url!r}. "
        f"Set VTF_SELFHOSTED_URL_PATTERNS or manually seed Repository before running migration."
    )
```

If the migration encounters an unmatched URL, it aborts loudly. Ops has two levers: add the self-hosted pattern to `VTF_SELFHOSTED_URL_PATTERNS`, or hand-seed the Repository row before running the migration. Silently defaulting to `raw_git` was rejected — it degrades to "everything import-only, no provider ops ever" which is hard to notice and harder to undo later.

The migration is idempotent: reruns skip already-migrated projects. Rollback is a single DELETE of rows created during this migration (recorded via a marker on `Repository.created_by_migration`).

### 13.5 Contract test suite

Guards the cutover at every state transition. A pytest suite (`tests/integration/test_repository_model_equivalence.py`) runs against a vtf instance in both modes and asserts:

```python
for project in Project.objects.all():
    legacy = old_get_repo_info(project.id)  # reads repo_url
    new = new_get_repo_info(project.id)     # reads primary Repository
    assert legacy.url == new.url
    assert legacy.default_branch == new.default_branch
    # ... all fields executor depends on
```

This suite is required-passing for any state transition.

---

## 14. Events & audit (P7)

Bootstrap emits a single compound event:

```json
{
  "id": "evt_...",
  "type": "project.bootstrapped",
  "timestamp": "2026-04-18T14:12:34Z",
  "actor": { "type": "user", "id": "alice", "username": "alice" },
  "acting_via": { "type": "user", "id": "vafi-agent", "username": "vafi-agent" },
  "subject": { "type": "project", "id": "proj_..." },
  "data": {
    "project": { "id": "proj_...", "name": "widgets" },
    "repositories": [
      { "id": "repo_...", "name": "main", "role": "primary", "url": "...", "mode": "create", "host": "github-main" },
      ...
    ],
    "members": [ { "user_id": "alice", "role": "owner" }, ... ],
    "workplan": { "id": "wp_...", "name": "Backlog" },
    "host_calls": [ { "host": "github-main", "op": "create_repo", "external_id": "123" } ]
  }
}
```

Consumers reconstruct what happened from one event rather than correlating across ten. Rollback events (§11.3) reference this event by id via `bootstrap_request_id`.

---

## 15. Testing strategy

### 15.1 Unit tests

- `ProjectService.bootstrap(...)` against `FakeHostDriver`: happy path, provider-create failure, DB failure after provider create, unknown user, unknown credential, capability mismatch, target-type mismatch, URL-pattern mismatch, scope denial, duplicate member, multi-repo create+import mix, empty repositories list rejected, more-than-one-primary rejected.
- `RollbackStack` behavior: LIFO order, continues after individual failures, emits orphan events.
- `CredentialService` scope enforcement across all three scope values.
- `GitHostService` capability validation.

### 15.2 Contract tests (driver-facing)

A shared `repo_hosts/contract_tests.py` parameterized over any `GitHostDriver` implementation. Covers:
- `create_repo` returns a `DriverRepoResult` with `clone_ready=True` when `auto_init_readme=True`.
- `delete_repo` is idempotent on already-deleted repos.
- `validate_reachable` returns True for a known-good URL, False for a known-bad one.
- `extra` fields unique to the host parse correctly (per-implementation subclass).
- `create_repo` with existing `(owner, name)` raises `RepoAlreadyExistsError`.
- Rate-limit / transient errors raise a documented exception class.

### 15.3 Integration tests (external)

`@pytest.mark.external` — run only when `VTF_RUN_EXTERNAL_TESTS=1`, against real provider APIs under a scratch org/namespace. CI job gated to `main` branch builds only.

### 15.4 API tests

HTTP-level tests against `POST /v1/projects/bootstrap/` with `FakeHostDriver` registered under a reserved `fake` kind. Covers every success/failure code from §9.1.

### 15.5 Cutover equivalence tests

§13.5. Gates every feature-flag state transition.

### 15.6 vafi-side tests

`CloneStrategy` dispatch unit tests with a fake `RepoInfo` DTO. Contract test: "for every kind published by vtf's `/v1/credential-kinds/`, vafi has a registered strategy."

---

## 16. Delivery slices (P10)

Six coherent, independently-shippable slices. Each has a single coherent deliverable; none depends on the next to be functionally correct.

| Slice | Scope | User-visible | Effort |
|-------|-------|--------------|--------|
| **0 — Impersonation prerequisite** | `On-Behalf-Of` middleware in vtf; `can_impersonate` permission model; grant to `vafi-agent`; dual-actor audit logging; bridge env-var wiring; pi-mcp-adapter header propagation; integration test proving human attribution works end-to-end. | No (infrastructure) | ~6h |
| **1a — Dormant infrastructure** | `RepoCredential`, `GitHost`, `Repository` models + migrations + model tests. Data migration seeding legacy credential + per-Project primary Repository. `Project.repo_url` remains authoritative. | No | ~12h |
| **1b — Read-side** | vafi executor reads from Repository when flag is `dual` or `new`; contract-test suite for `get_repo_info` equivalence between paths. Runs behind flag `off` by default. | No | ~12h |
| **1c — Write-side (import-only)** | `POST /v1/projects/bootstrap/` accepting `mode=import` only. Admin CRUD for credentials and hosts. Discovery endpoints. `vtf_bootstrap_project` MCP tool with `mode=import`. Auth/scope enforcement. API-test suite. | **Yes** — architect can bootstrap projects against existing repos | ~18h |
| **1d — Cutover** | Flag → `new`; monitor §13.3 stop criteria; drop `Project.repo_url` and `Project.default_branch` columns in a follow-up migration once criteria are met. | No (operational) | ~4h |
| **2 — GitHub driver + create mode** | `GitHubDriver` implementation + contract test suite + integration test against real github.com test org + `mode=create` end-to-end in bootstrap + rollback-on-failure wired + ops doc for `VTF_GITHUB_TOKEN` provisioning. | Yes — architect can bootstrap greenfield projects on GitHub | ~14h |

**Phase 1 (Slices 0 + 1a + 1b + 1c + 1d): ~52h.**
**Phase 2: +14h.**
**Phases 3+ (GitLab, Bitbucket, additional clone strategies): ~4h per driver.**

Why this order: Slice 0 is a prerequisite because its absence means every architect-bootstrapped project has the wrong owner. Slice 1a is dormant so it cannot break production. Slice 1b is readonly behind a flag, so no production impact. Slice 1c is the first user-visible deliverable; by construction, no production path depends on it until the flag moves. Slice 1d is operational only. Phase 2 is a net-new capability; breaks nothing existing.

---

## 17. Items requiring verification or operator decision

Not design choices — verifiable facts or ops-domain decisions. Listed for completeness of the plan, not for reopening architectural discussion.

1. **`vafi-agent` user exists and can be granted permissions.** Trivially true from `create-secrets.sh`; confirm the migration that adds `can_impersonate` works against the prod user table.
2. **Each namespace's Secret sync story.** Cluster-ops decides: manual? ExternalSecrets operator? Sealed Secrets? Affects operational runbook, not design.
3. **GitHub bot token provisioning for Slice 2.** PAT on a bot user vs GitHub App. GitHub App is the better long-term answer but more complex to set up. Decision for ops when Slice 2 begins.
4. **Naming of the legacy credential seeded by migration.** The design uses `legacy-github-ssh`. Trivially bike-shed; leaving decision to review.
5. **Initial `ENABLE_PROJECT_SCOPED_CREDENTIALS`** default — `false` in v1 per §8.2.

---

## 18. Alternatives considered

### 18.1 Keep `Project.repo_url`, add a sibling `Project.additional_repo_urls: JSONB`

Pros: minimal schema change. Cons: no credential binding per repo, no clone options per repo, no role (primary/secondary) modeling, every future enhancement requires another JSON field. Rejected: the single-column-plus-list approach scales to "two repos with the same auth" and nothing beyond.

### 18.2 Subclass `RepoCreateSpec` per kind (`GitHubRepoCreateSpec`, `GitLabRepoCreateSpec`)

Pros: static typing of kind-specific fields. Cons: the endpoint must dispatch on kind before validation runs, leaking driver-awareness back into the API layer; serializer selection becomes kind-conditional. Violates OCP at the API surface. Rejected in favor of flat `RepoCreateSpec` + `extra: dict` + per-driver `validate_spec`.

### 18.3 One unified `Credential` table for both user auth and repo auth

Pros: fewer tables. Cons: user auth and repo auth have different lifecycles, different capability models, different APIs, different audit requirements. Conflating them creates a model that doesn't satisfy either well. Rejected; `RepoCredential` is separate and namespaced.

### 18.4 Async bootstrap with job polling

Pros: fast endpoint response. Cons: atomicity across external side effects + DB transaction is much harder with async hand-offs; callers must poll; simple human-paced operation grows infrastructure. Rejected for v1; revisit only if P95 latency exceeds 10s.

### 18.5 `owner_user_id` parameter on bootstrap (workaround for missing impersonation)

Considered during ultrathink. Rejected as papering over a broken identity layer. See §8.1 — impersonation is the right fix and belongs in scope.

### 18.6 Single aggregate for Project + RepoCredential + GitHost

Pros: simpler transaction boundaries. Cons: credentials and hosts have cross-project scope and independent lifecycles; forcing them into the Project aggregate forbids shared credentials and complicates credential CRUD. Rejected; three aggregates is correct by DDD criteria.

### 18.7 Per-call provider instantiation via callable, not classes

Pros: avoids OO ceremony. Cons: loses `ClassVar` capability declarations, complicates contract-test parametrization, no natural place for per-driver helpers. Rejected; driver classes are the right fit.

---

## 19. Work items

Each maps to a slice above. Each is sized to fit within a focused PR.

**Slice 0**
- `vtf-impersonation-1` On-Behalf-Of middleware + `can_impersonate` permission + audit dual-actor recording
- `vafi-impersonation-1` Bridge passes `VF_ON_BEHALF_OF` env var
- `vafi-impersonation-2` pi-mcp-adapter propagates `On-Behalf-Of` header
- `test-impersonation-1` End-to-end: human → bridge → architect pod → vtf → audit shows correct actor

**Slice 1a**
- `vtf-model-1` `RepoCredential` model, serializers, migration
- `vtf-model-2` `GitHost` model, serializers, migration
- `vtf-model-3` `Repository` model, serializers, migration
- `vtf-model-4` Data migration: seed legacy credential + primary Repository per Project
- `vtf-model-5` Dual-write signals for `Project.repo_url` ↔ primary Repository

**Slice 1b**
- `vafi-executor-1` Refactor `get_repo_info` to read from Repository behind feature flag
- `vafi-executor-2` `CloneStrategy` interface + `SshKeyStrategy` + `PublicStrategy` + registry
- `vafi-executor-3` Refactor `_ensure_repo_cloned` to dispatch on strategy
- `test-equivalence-1` Contract test: `get_repo_info` equivalence across flag states

**Slice 1c**
- `vtf-api-1` `POST /v1/projects/bootstrap/` + `/v2/projects/bootstrap/` (`mode=import` only)
- `vtf-api-2` Credential CRUD (+ scope enforcement)
- `vtf-api-3` GitHost CRUD (+ base_url allowlist check)
- `vtf-api-4` Discovery endpoints (`/hosts/`, `/credentials/`, `/credential-kinds/`, `/host-kinds/`, `/repository-model/`)
- `vtf-api-5` `GET /v1/repositories/{id}/clone-info/` (vafi-facing)
- `vtf-mcp-1` `vtf_bootstrap_project` + `vtf_list_hosts` + `vtf_list_credentials` + `vtf_add_repository` + `vtf_list_repositories` + `vtf_set_primary_repository` + `vtf_delete_repository`
- `vtf-events-1` `ProjectBootstrappedEvent` + audit integration
- `vtf-tests-1` API test suite covering all error codes from §9.1
- `vafi-vfctl-1` New `vfctl clone <repo-name>` helper in `vafi/src/vfctl/` — resolves project context from env, calls clone-info endpoint, dispatches via `CloneStrategy`

**Slice 1d**
- `ops-cutover-1` Telemetry dashboards for §13.3 stop criteria
- `vtf-migration-drop` Follow-up migration dropping `Project.repo_url` + `Project.default_branch` (lands only after criteria met)

**Slice 2**
- `vtf-driver-github-1` `GitHubDriver` implementation
- `vtf-driver-github-2` Contract test suite (reusable for future drivers)
- `vtf-driver-github-3` Integration tests against test org
- `vtf-api-5` `mode=create` handling in bootstrap + `RollbackStack` wired
- `ops-github-1` Ops doc for `VTF_GITHUB_TOKEN` provisioning (PAT vs GitHub App)

---

## 20. References

- Fowler, "Strangler Fig Application" — pattern for the migration strategy
- Evans, *Domain-Driven Design* — aggregate design
- Vlissides et al., *Design Patterns* — Strategy, Registry, Factory patterns used throughout
- OAuth 2.0 Token Exchange (RFC 8693) — informs the On-Behalf-Of mechanism
- Current vtf design docs listed in the header
