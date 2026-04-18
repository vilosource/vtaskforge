# Project Bootstrap — Provider-Agnostic Design

**Date:** 2026-04-18
**Status:** Draft
**Author:** claude (session 2026-04-18, follow-up to architect-E2E discussion)
**Related:**
- `docs/design/project-hierarchy-DESIGN.md` — Project model
- `docs/design/phase4c-mcp-redesign-DESIGN.md` — MCP tool style
- `vafi/docs/vtf-vafi-interface-CONTRACT.md` — how vafi executors consume vtf state

---

## 1. Problem

Creating a new project that the vafi fleet can actually work on requires five conditions, all of which must be true:

1. A `Project` row in vtf with valid `repo_url` and `default_branch`
2. A git repository at that URL, reachable from executor pods
3. SSH/token credentials in the cluster (`github-ssh` secret) grant read+write to that repo
4. A non-empty default branch (git clone of an empty repo leaves no HEAD and breaks context build)
5. `ProjectMembership` for `vafi-agent` so executors can claim tasks

Today only #1 and #5 are achievable through vtf's API. The rest require out-of-band steps (human uses the git host's web UI, ops wires secrets, etc.). This breaks the architect-driven workflow: an architect agent cannot bootstrap a project end-to-end, because vtf doesn't own the repo-creation primitive.

Moreover, hardcoding "GitHub" into vtf would foreclose future use of GitLab, Bitbucket, Gitea, or self-hosted git servers. Viloforge needs provider-pluggability from the start.

### Motivating flow

A human user, working with an interactive architect session:

> **User:** Start a new project called `widgets-api`. Use GitLab, namespace `viloforge`. Add me and `vafi-agent` as members. Put a `Backlog` workplan in it so I can start filing tasks.

Today, this requires the user to: (a) create the GitLab repo by hand, (b) copy the URL, (c) ask the architect to create the vtf Project row, (d) manually add memberships. Four side-channel steps the architect can't see or verify. After this design lands: a single MCP call, all of it atomic.

---

## 2. Goals & non-goals

### Goals

- **Atomic bootstrap**: Project + git repo + memberships + (optional) initial workplan created in a single operation. Partial failures roll back as far as the underlying systems permit.
- **Provider-pluggable**: GitHub, GitLab, Bitbucket, Gitea, and future hosts are added without modifying the orchestrator, the API endpoint, the MCP tool, or any tests that don't target the specific provider.
- **Two modes**: `create` (vtf creates a new repo via the provider) and `import` (caller points vtf at an existing repo; vtf only records it and wires memberships).
- **Introspectable**: Clients (especially the architect) can query which providers are registered and what their capability set / spec schema is.
- **Auth-clean**: All bootstrap calls flow through the same `RoleBasedPermission` / `ProjectMembership` machinery as the rest of the API. No side channel.

### Non-goals (v1)

- **User/identity provisioning.** `members[]` references existing users only.
- **k8s secret management.** Provisioning `github-ssh` / `harbor-registry` per new repo stays a cluster-ops concern.
- **CI/CD scaffolding.** No GitHub Actions, no GitLab CI pipelines, no branch protection rules.
- **Cross-provider migrations.** Moving a project from GitHub to GitLab later is out of scope.
- **Mirror / replica repos**, bare-git-on-NFS providers, federated identity.
- **Async bootstrap.** The endpoint is synchronous. Repo creation takes 1–3s from a real provider; acceptable for a rare, human-triggered operation.

---

## 3. Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│                   Callers (provider-agnostic)                    │
│    REST client  │  MCP tool  │  vtf CLI  │  Web UI (future)      │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│   POST /v1/projects/bootstrap/  (projects/bootstrap/views.py)    │
│   GET  /v1/providers/           (repo_providers/views.py)        │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│             ProjectBootstrapService (orchestrator)               │
│   - transaction.atomic around DB writes                          │
│   - RollbackStack for best-effort external rollback              │
│   - Delegates all repo work to registered RepoProvider           │
└─────────────────────────────┬────────────────────────────────────┘
                              │ depends only on abstract
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      RepoProvider (abstract)                     │
│   capabilities: frozenset[Capability]                            │
│   validate_spec, create_repo, delete_repo, validate_reachable    │
└─────┬─────────────────────┬─────────────────┬────────────────────┘
      │                     │                 │
      ▼                     ▼                 ▼
  GitHubProvider       GitLabProvider   BitbucketProvider
  (phase 2)            (phase 3)        (phase 3+)
```

### SOLID mapping

| Principle | Realization |
|-----------|-------------|
| **Single Responsibility** | Orchestrator owns vtf-DB atomicity; each provider owns one git host's REST idiosyncrasies; registry owns discovery. No class has two reasons to change. |
| **Open/Closed** | Adding a provider is a new class + one registration line. No core code modified. |
| **Liskov** | Providers honor one abstract contract. Provider-specific capabilities are declared via a `Capability` flag set, not detected via `isinstance`. |
| **Interface Segregation** | `RepoProvider` is split into mixin-like roles (`RepoCreator`, `RepoValidator`, `RepoDeleter`, `DeployKeyManager`, `WebhookRegistrar`). Providers implement what they support; clients depend only on what they call. |
| **Dependency Inversion** | The orchestrator depends on the `RepoProvider` ABC. Concrete providers are wired at app boot. Tests inject a `FakeRepoProvider`. |

---

## 4. Domain model changes

### 4.1 `Project` model

Two new columns:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `provider` | `CharField(max_length=50, null=True)` | `None` | Name of the registered `RepoProvider` that owns this project's repo. Nullable for backward compatibility with projects that predate bootstrap. |
| `provider_external_id` | `CharField(max_length=255, null=True)` | `None` | Provider-native ID (GitHub numeric repo id, GitLab path, etc.) for idempotent future operations (e.g. delete, rename). |

Migration: additive, nullable, no backfill required.

### 4.2 New directory structure

```
src/
├── projects/
│   └── bootstrap/
│       ├── __init__.py
│       ├── service.py              # ProjectBootstrapService
│       ├── spec.py                 # BootstrapSpec, RepoSpec dataclasses
│       ├── serializers.py          # DRF serializers for the endpoint
│       ├── views.py                # BootstrapView
│       └── rollback.py             # RollbackStack
└── repo_providers/
    ├── __init__.py                 # public API, re-exports registry
    ├── base.py                     # RepoProvider ABC, Capability, Repo, RepoSpec
    ├── registry.py                 # ProviderRegistry singleton
    ├── contract_tests.py           # Shared pytest suite for every provider
    ├── views.py                    # GET /v1/providers/
    ├── github/
    │   ├── __init__.py
    │   ├── provider.py
    │   ├── client.py
    │   └── config.py
    ├── gitlab/                      # phase 3
    └── fake/                        # in-process provider for tests
        └── provider.py
```

---

## 5. Provider interface

### 5.1 Core types

```python
# repo_providers/base.py
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Optional


class Capability(str, Enum):
    CREATE_REPO       = "create_repo"
    DELETE_REPO       = "delete_repo"
    AUTO_INIT         = "auto_init"          # provider can seed README/initial commit
    DEPLOY_KEYS       = "deploy_keys"
    WEBHOOKS          = "webhooks"
    BRANCH_PROTECTION = "branch_protection"
    VALIDATE_REACH    = "validate_reachable" # provider can verify a URL + credential pair
    RENAME            = "rename"
    TRANSFER          = "transfer"


@dataclass(frozen=True)
class RepoSpec:
    """Provider-agnostic creation spec. `extra` is the escape hatch for
    provider-specific fields that don't generalize (validated by the
    target provider only)."""
    name: str                         # repo name in the host
    owner: str                        # GitHub org/user, GitLab namespace, etc.
    description: str = ""
    private: bool = True
    default_branch: str = "main"
    auto_init_readme: bool = True
    extra: dict | None = None         # provider-validated


@dataclass(frozen=True)
class Repo:
    """What the orchestrator stores and returns."""
    url: str                          # canonical SSH URL
    https_url: str                    # for display
    default_branch: str
    provider: str                     # registered provider name
    external_id: str                  # host-native id
    clone_ready: bool                 # default branch exists with >= 1 commit


class RepoProvider(ABC):
    """Base class. Implementations declare which capabilities they support
    via the `capabilities` class attribute. The orchestrator checks
    capability before invoking any optional method."""

    name: ClassVar[str]
    capabilities: ClassVar[frozenset[Capability]]

    @abstractmethod
    def validate_spec(self, spec: RepoSpec) -> None:
        """Raise ValidationError (DRF-compatible) if spec is invalid for this provider."""

    @abstractmethod
    def create_repo(self, spec: RepoSpec) -> Repo:
        """Create a new repo. Must be called only if CREATE_REPO ∈ capabilities."""

    @abstractmethod
    def delete_repo(self, repo: Repo) -> None:
        """Delete a repo. Optional; caller must check capability first."""

    @abstractmethod
    def validate_reachable(self, url: str) -> bool:
        """Check a repo URL is reachable with the provider's configured credential.
        Used for `mode: import`. Optional capability."""
```

### 5.2 Why `extra: dict` instead of subclassing `RepoSpec`?

An inheritance hierarchy (`GitHubRepoSpec`, `GitLabRepoSpec`, …) would violate the generic API surface — the endpoint would need to dispatch on provider to pick the right schema before DRF validation. Keeping `RepoSpec` flat and letting each provider's `validate_spec` consume `extra` keeps the API uniform and pushes provider-specifics behind the interface.

The tradeoff: `extra` is a stringly-typed escape hatch. Each provider's contract test must cover its `extra` parsing to prevent silent drift. This is an acceptable tradeoff given how rarely `extra` is needed (most providers accept the normalized spec verbatim).

---

## 6. Provider registry

```python
# repo_providers/registry.py
class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, RepoProvider] = {}

    def register(self, provider: RepoProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Provider '{provider.name}' already registered")
        self._providers[provider.name] = provider

    def get(self, name: str) -> RepoProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise UnknownProviderError(name, available=list(self._providers))

    def list_providers(self) -> list[RepoProvider]:
        return list(self._providers.values())


registry = ProviderRegistry()
```

### Registration at boot

```python
# projects/apps.py or a new repo_providers/apps.py
from django.apps import AppConfig

class RepoProvidersConfig(AppConfig):
    name = "repo_providers"

    def ready(self):
        from repo_providers.registry import registry
        from django.conf import settings

        for provider_name in settings.ENABLED_REPO_PROVIDERS:
            if provider_name == "github":
                from repo_providers.github import GitHubProvider
                registry.register(GitHubProvider.from_settings(settings))
            elif provider_name == "gitlab":
                from repo_providers.gitlab import GitLabProvider
                registry.register(GitLabProvider.from_settings(settings))
            # Adding Bitbucket later is: new elif branch. Nothing else changes.
```

Settings:

```python
# settings/base.py
ENABLED_REPO_PROVIDERS = ["github"]           # list; order doesn't matter
VTF_GITHUB_TOKEN = os.environ.get("VTF_GITHUB_TOKEN", "")
VTF_GITHUB_DEFAULT_OWNER = os.environ.get("VTF_GITHUB_DEFAULT_OWNER", "")
```

---

## 7. Bootstrap service

```python
# projects/bootstrap/service.py
class ProjectBootstrapService:
    def __init__(self, providers: ProviderRegistry = None, members: MemberService = None):
        self._providers = providers or registry
        self._members = members or MemberService()

    def bootstrap(self, spec: BootstrapSpec, actor: User) -> Project:
        if spec.mode == "create":
            return self._bootstrap_create(spec, actor)
        elif spec.mode == "import":
            return self._bootstrap_import(spec, actor)
        else:
            raise ValueError(f"Unknown bootstrap mode: {spec.mode}")

    def _bootstrap_create(self, spec: BootstrapSpec, actor: User) -> Project:
        provider = self._providers.get(spec.repo.provider)
        if Capability.CREATE_REPO not in provider.capabilities:
            raise ProviderCapabilityError(provider.name, Capability.CREATE_REPO)
        provider.validate_spec(spec.repo_spec())

        rollback = RollbackStack()
        try:
            # External side-effect first so we can short-circuit on provider failure
            repo = provider.create_repo(spec.repo_spec())
            if Capability.DELETE_REPO in provider.capabilities:
                rollback.push(lambda: provider.delete_repo(repo))
            else:
                rollback.push_manual_marker(f"orphan repo created: {repo.url}")

            with transaction.atomic():
                project = self._create_project_rows(spec, repo, actor)
                self._members.add_all(project, spec.members, actor)
                if spec.initial_workplan:
                    self._create_initial_workplan(project, spec.initial_workplan)

            return project

        except Exception:
            rollback.run_best_effort()  # logs failures, emits events
            raise

    def _bootstrap_import(self, spec: BootstrapSpec, actor: User) -> Project:
        # No external side-effect. Pure DB transaction.
        if spec.repo.provider:
            provider = self._providers.get(spec.repo.provider)
            if Capability.VALIDATE_REACH in provider.capabilities:
                if not provider.validate_reachable(spec.repo.url):
                    raise RepoUnreachableError(spec.repo.url)

        with transaction.atomic():
            project = self._create_project_rows(spec, repo=None, actor=actor)
            self._members.add_all(project, spec.members, actor)
            if spec.initial_workplan:
                self._create_initial_workplan(project, spec.initial_workplan)

        return project
```

The orchestrator never mentions `github`, `gitlab`, or any concrete provider. It speaks only to the ABC.

---

## 8. API surface

### 8.1 `POST /v1/projects/bootstrap/`

**Create mode:**

```json
{
  "name": "widgets-api",
  "description": "Widget REST service",
  "mode": "create",
  "repo": {
    "provider": "gitlab",
    "owner": "viloforge",
    "repo_name": "widgets-api",
    "private": true,
    "default_branch": "main",
    "auto_init_readme": true,
    "extra": { "visibility": "internal" }
  },
  "members": [
    { "user_id": "vafi-agent", "role": "member" },
    { "user_id": "alice",      "role": "owner"  }
  ],
  "initial_workplan": { "name": "Backlog", "description": "" }
}
```

**Import mode:**

```json
{
  "name": "my-existing-app",
  "mode": "import",
  "repo": {
    "provider": "github",
    "url": "git@github.com:vilosource/my-existing-app.git",
    "default_branch": "main"
  },
  "members": [
    { "user_id": "vafi-agent", "role": "member" }
  ]
}
```

**Response (201 Created):**

```json
{
  "project": { /* full v2 project shape */ },
  "repo": {
    "url": "git@gitlab.com:viloforge/widgets-api.git",
    "provider": "gitlab",
    "default_branch": "main",
    "clone_ready": true
  },
  "members": [ /* membership records */ ],
  "workplan": { /* full v2 workplan shape, if initial_workplan given */ }
}
```

**Error responses:**

| Status | Code | Meaning |
|--------|------|---------|
| 400    | `VALIDATION_ERROR`      | spec validation failed (including provider-specific `extra` rules) |
| 400    | `UNKNOWN_USER`          | one or more `members[*].user_id` does not exist |
| 400    | `UNKNOWN_PROVIDER`      | requested provider not registered in this deployment |
| 400    | `MISSING_CAPABILITY`    | provider doesn't support the requested operation (e.g. `create_repo`) |
| 401    | `AUTHENTICATION_REQUIRED` | no authenticated caller |
| 403    | `FORBIDDEN`             | caller lacks project-create permission (if such a gate exists) |
| 409    | `REPO_ALREADY_EXISTS`   | provider rejected create because (owner, name) is taken |
| 409    | `PROJECT_URL_TAKEN`     | vtf already has a project with that `repo_url` (import mode) |
| 422    | `PROVIDER_ERROR`        | provider API returned an unexpected error; orphan-cleanup attempted |
| 502    | `PROVIDER_UNREACHABLE`  | network/timeout failure talking to the provider |

### 8.2 `GET /v1/providers/`

```json
{
  "providers": [
    {
      "name": "github",
      "capabilities": ["create_repo", "delete_repo", "auto_init", "deploy_keys", "webhooks", "validate_reachable"],
      "spec_schema": { /* JSON Schema for RepoSpec fields this provider accepts, including `extra` */ }
    },
    {
      "name": "gitlab",
      "capabilities": ["create_repo", "delete_repo", "auto_init", "webhooks", "validate_reachable"],
      "spec_schema": { ... }
    }
  ]
}
```

This is what the architect introspects before prompting the user.

---

## 9. MCP tool

```python
# mcp_server/tools/project_bootstrap.py
@mcp.tool()
@handle_errors
@serialize_response
def vtf_bootstrap_project(
    name: str,
    mode: str = "import",
    description: str = "",
    repo_provider: str = "",
    repo_owner: str = "",
    repo_name: str = "",
    repo_url: str = "",
    repo_private: str = "true",
    repo_default_branch: str = "main",
    repo_auto_init_readme: str = "true",
    repo_extra: str = "",
    members: str = "",                 # JSON array
    initial_workplan_name: str = "",
    initial_workplan_description: str = "",
) -> dict:
    """Bootstrap a new project with repo, members, and optional initial workplan.

    mode=create: create a new repo via the named provider.
    mode=import: point vtf at an existing repo (repo_url required).

    members: JSON array of {"user_id": "<id>", "role": "<owner|member|viewer>"}.
    """
```

Tool marshals the flat MCP argument list into a `BootstrapSpec` and delegates to `ProjectBootstrapService`.

A second tool, `vtf_list_providers`, wraps `GET /v1/providers/` so an architect can discover options mid-conversation.

---

## 10. Failure semantics & rollback

`create` mode has a two-phase operation (external repo + DB rows). Failure modes:

| Phase that fails | What's on disk | Action |
|------------------|---------------|--------|
| Spec validation (local) | nothing | Return 400, no cleanup |
| Provider rejects create | nothing | Return appropriate status, no cleanup |
| Provider creates repo, DB tx fails | provider has repo, vtf has no project | Call `provider.delete_repo(repo)` if capability present; emit `manual_cleanup_required` event otherwise |
| Provider creates repo, DB commits, member grant fails mid-way | vtf project exists, repo exists, some memberships missing | DB rolls back the project + any partial memberships (all inside `transaction.atomic`); provider rollback also runs |
| Provider creates repo, DB succeeds, later caller fails | Everything exists | No rollback — operation completed |

`import` mode is pure DB; no external rollback needed.

### `RollbackStack`

```python
class RollbackStack:
    """LIFO cleanup for external side effects that happened before a DB
    transaction failed. Best-effort — cleanup failures emit events but
    do not shadow the original exception."""

    def push(self, action: Callable[[], None]) -> None: ...
    def push_manual_marker(self, note: str) -> None: ...
    def run_best_effort(self) -> None: ...
```

Every `push_manual_marker` call emits an `OrphanResourceEvent` so operators have a structured log of things to clean up by hand (e.g. for providers without programmatic delete).

---

## 11. Security & auth

### Caller auth

Uses the existing `TokenAuthMiddleware` + `RoleBasedPermission` stack. Bootstrap is treated as a project-create action; the caller must be authenticated. There is no project-level membership check at bootstrap time (the project doesn't exist yet), but:

- The caller is automatically added as `owner` if not already in `members[]`.
- Staff users bypass any additional gates (consistent with the rest of vtf).
- A future `ENABLE_BOOTSTRAP_GATE` setting could require a specific global role (e.g. staff only), but v1 treats any authenticated user as bootstrap-capable.

### Provider credentials

Each provider reads its credentials from Django settings at boot:

- `VTF_GITHUB_TOKEN` — a PAT or GitHub App installation token with `repo` scope
- `VTF_GITHUB_DEFAULT_OWNER` — default owner for repos, can be overridden per-spec
- `VTF_GITLAB_TOKEN` / `VTF_GITLAB_URL` — when GitLab lands
- `VTF_BITBUCKET_APP_PASSWORD` / `VTF_BITBUCKET_WORKSPACE` — when Bitbucket lands

In prod, these are mounted as env vars from a Kubernetes Secret (same pattern as `vafi-secrets`). Credential rotation is handled by rotating the secret + restarting the vtf API pod. Not implementing in-app rotation in v1.

### What a compromised vtf token can do

Same as today for existing projects, plus: bootstrap new projects (with caller as owner) and trigger provider API calls on vtf's credentials. Rate-limiting provider calls (e.g. max 10 bootstraps/hour per user) is a follow-up hardening.

---

## 12. Testing strategy

### 12.1 Unit tests

- `ProjectBootstrapService` with `FakeRepoProvider` covering: happy path, provider-create failure, DB failure after provider create, unknown user in members, duplicate member, unknown provider, missing capability, duplicate project URL, import mode with reachable repo, import mode with unreachable repo.

### 12.2 Contract tests

`repo_providers/contract_tests.py` — a parameterizable pytest suite that every real provider runs against a scratch namespace. Covers:

- `create_repo` returns a `Repo` with `clone_ready=True` when `auto_init_readme=True`
- `delete_repo` idempotent on already-deleted repos
- `validate_reachable` returns True for a known-good URL, False for a known-bad one
- `extra` fields unique to the provider parse correctly
- `create_repo` with an existing `(owner, name)` raises `RepoAlreadyExistsError`
- Rate-limit / transient errors raise a documented exception class

Providers wire into it with one line:

```python
# tests/repo_providers/test_github_provider.py
from repo_providers.contract_tests import make_contract_tests
from repo_providers.github import GitHubProvider

GitHubProviderContractTests = make_contract_tests(
    provider=GitHubProvider.from_settings(settings),
    scratch_owner="viloforge-test",
)
```

### 12.3 Integration tests

`@pytest.mark.external` — skipped unless `VTF_RUN_EXTERNAL_TESTS=1`. CI job opted in for the `main` branch only; not run on every PR.

### 12.4 API tests

End-to-end HTTP tests against `POST /v1/projects/bootstrap/` using the `FakeRepoProvider` registered under a test-only provider name. Cover:

- Successful create mode → project, repo, members, workplan all present
- Successful import mode → project + members only
- Auth failure → 401
- Unknown provider → 400
- Provider without `create_repo` capability + `mode: create` → 400

---

## 13. Provider specifics

### 13.1 GitHub (phase 2)

- Uses `httpx` against `https://api.github.com`
- Auth: bearer token
- `create_repo`: `POST /orgs/{owner}/repos` or `POST /user/repos` depending on owner type
- `auto_init_readme=True` ⇒ `auto_init: true` in payload; response includes the seeded commit
- `delete_repo`: `DELETE /repos/{owner}/{name}` — requires `delete_repo` scope on the token, which not all tokens have; capability flag reflects this per-token
- `validate_reachable`: `GET /repos/{owner}/{name}` ⇒ 200/404
- **Deploy keys**: if the org-wide SSH key already has access to the new repo (true for Viloforge today), skip. Capability gate is `DEPLOY_KEYS`; not advertised by default.

### 13.2 GitLab (phase 3)

- Different auth: `PRIVATE-TOKEN` header
- `create_repo`: `POST /api/v4/projects` — note field name is `path`, not `name`; validated via `extra` or normalized on entry
- `auto_init_readme`: `initialize_with_readme: true`
- Namespaces vs users: both accepted; owner field maps to `namespace_id` lookup

### 13.3 Bitbucket (phase 3+)

- Different auth: app password + username
- Workspaces replace orgs; `owner` maps to workspace
- No programmatic delete on free tier — advertise without `DELETE_REPO` capability
- **Implication**: rollback of bootstrap against Bitbucket leaves orphan repos; operators see structured events

### 13.4 Gitea / self-hosted (future)

- `base_url` becomes a per-provider config field
- API surface similar to GitHub's

---

## 14. Delivery plan

| Phase | Scope | Estimate |
|-------|-------|----------|
| **1** | Interface + registry + `FakeRepoProvider` + `ProjectBootstrapService` + serializers + endpoint + `GET /v1/providers/` + `vtf_bootstrap_project` + `vtf_list_providers` MCP tools + unit tests + API tests. `import` mode works end-to-end; `create` mode gated on Phase 2. | ~8h |
| **2** | `GitHubProvider` + config loader + contract test suite + rollback-on-DB-failure + integration tests (`@pytest.mark.external`) + ops doc on provisioning `VTF_GITHUB_TOKEN`. | ~8h |
| **3** | `GitLabProvider`. Straightforward once the pattern is proven. | ~4h |
| **4** | `BitbucketProvider`. Same. | ~4h |
| **Future** | `GiteaProvider`, `LocalGitProvider`, webhook registration, branch protection. Add as needed. | on demand |

Phase 1 is the most important phase. If Phase 1's abstractions are wrong, every subsequent phase suffers. Phase 1 lands with zero real providers registered — only `FakeRepoProvider` in tests — and that's intentional: it proves the abstraction doesn't secretly assume GitHub.

---

## 15. Open questions

1. **URL canonicalization.** If `import` mode accepts `https://github.com/org/repo`, normalize to the SSH form (since executors clone via `github-ssh`)? Or accept both and store whichever was given? **Lean:** store SSH canonical, compute HTTPS on display. Providers own the parsing.

2. **Credential scoping.** Single global token per provider, or per-project tokens? Global is simpler; per-project is more secure and matches multi-tenant ambitions. **Lean:** v1 global; schema is designed so a `project.provider_credential_ref` column could be added later without breaking anyone.

3. **`vafi-agent` auto-grant.** Should vtf automatically add `vafi-agent` with `member` role to every bootstrapped project (as a fleet invariant), or require it in `members[]` explicitly? **Lean:** auto-grant with a `skip_vafi_agent: true` opt-out. Forgetting it means no executor can claim tasks — a silent broken state that's worth preventing.

4. **Default owner.** If `repo.owner` is omitted in `create` mode, fall back to `VTF_GITHUB_DEFAULT_OWNER` (or equivalent per provider)? **Lean:** yes, it's what architect flows want. Explicit in spec beats implicit default.

5. **Idempotency.** If a caller POSTs the same bootstrap twice (network retry), GitHub returns 422 on the second call. Should vtf treat that as success (the repo exists, maybe create the Project row pointing at it)? **Lean:** no — too easy to paper over real conflicts. Surface the 409 clearly. An `idempotency_key` header is a follow-up hardening.

6. **Provider removal.** If an operator removes GitLab from `ENABLED_REPO_PROVIDERS` while projects with `provider="gitlab"` still exist, what happens? **Lean:** project reads still work (the data is all in `repo_url`); provider-dependent operations (future delete-project-repo) fail with `UNKNOWN_PROVIDER`. Document this.

7. **Telemetry.** Metrics on `bootstrap.create.success`, `bootstrap.create.provider_error`, `bootstrap.rollback.invoked`, `bootstrap.rollback.failed` — useful for ops. **Lean:** add in Phase 2 once real provider traffic exists.

---

## 16. Alternatives considered

### 16.1 "Leave it to the CLI / a separate provisioner service"

Pros: vtf stays a pure task-tracker. Cons: bootstrap becomes a federation of scripts with no shared audit trail, no shared auth model, no shared error handling. Architect flows become multi-call dances across systems, breaking the single-MCP-call UX goal.

### 16.2 "Subclass `RepoSpec` per provider"

Pros: static typing of provider-specific fields. Cons: endpoint and serializer must dispatch on provider before validation can run, leaking provider-awareness back into the orchestrator. Violates OCP.

### 16.3 "One fat `GitHostProvider` interface"

Pros: fewer types. Cons: every provider has to stub methods for capabilities it doesn't support, either with `NotImplementedError` or silently succeeding. Forces clients to know which providers support what. Violates ISP.

### 16.4 "Async bootstrap via Celery"

Pros: endpoint returns immediately. Cons: atomicity becomes much harder (repo created in task N, project rows created in task N+1), the client has to poll for completion, and a simple human-paced operation grows infrastructure. Revisit only if repo creation P95 exceeds 10s.

---

## 17. Work items to open after approval

1. **vtf-001** Scaffolding + `FakeRepoProvider` + unit test harness. (Phase 1)
2. **vtf-002** `BootstrapSpec` + serializers + `POST /v1/projects/bootstrap/` + API tests in `import` mode. (Phase 1)
3. **vtf-003** `GET /v1/providers/`. (Phase 1)
4. **vtf-004** `vtf_bootstrap_project` + `vtf_list_providers` MCP tools + mcp-server-README updates. (Phase 1)
5. **vtf-005** `GitHubProvider` + contract test suite + rollback path + ops doc. (Phase 2)
6. **vtf-006** E2E test: architect session bootstraps a project on GitHub, fleet runs a chained workplan in it, asserts commit lands. (Phase 2 — this is the full vfleet E2E the original question was asking about.)
7. **vtf-007** `GitLabProvider` + contract tests. (Phase 3)
8. **vtf-008** `BitbucketProvider` + contract tests + document no-programmatic-delete limitation. (Phase 4)
