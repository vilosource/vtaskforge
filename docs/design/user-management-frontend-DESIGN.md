# User Management Interfaces — Design

## Problem

vtaskforge has a complete backend for user management (6 phases, 73 tests, 7 API endpoints) but none of the three interfaces — web, MCP, or CLI — expose it. The backend was built API-first, but every consumer interface was skipped.

**For regular users** (web), there is no way to:
- See who they are or what projects they belong to
- View their session history with agents
- Link or manage external identities (Slack, WhatsApp)
- See their recent activity beyond the Home page widget

**For administrators** (web), there is no way to:
- View or manage users without shelling into Django admin
- Add or remove project members, or change their roles
- See or release agent locks that may be stale
- Create or manage service accounts
- Map external channels (Slack channels, etc.) to projects
- See who has access to what across the platform

**For agents** (MCP), there is no way to:
- Query who they are or what project they're operating in
- Acquire, release, or check agent locks through tools
- Resolve a channel to a project
- Look up external identity mappings
- List project members or check permissions

**For operators** (CLI), there is no way to:
- Inspect or manage users, locks, or memberships from the terminal
- Create service accounts without a Django management command
- Audit who has access to what
- Troubleshoot stale locks or broken channel mappings

This means that every user management action today requires either Django admin access or a management command (`create_service_account`), making vtf operationally dependent on a developer with shell access. As vtf grows into the identity provider for the viloforge platform, this gap becomes a blocker for self-service onboarding, agent autonomy, and day-to-day administration.

### What Exists Today

| Layer | Status |
|-------|--------|
| **Models** | Complete — UserProfile, ExternalIdentity, SessionRecord, AgentLock, ChannelProjectMapping, ProjectMembership (`src/prefs/models.py`) |
| **Services** | Minimal — `get_or_create_profile()`, `record_access()`, `create_service_account()` (`src/prefs/services.py`) |
| **API endpoints** | 7 endpoints live — token validation, recent access, session history, external identities (CRUD), locks (CRUD), channel mappings (CRUD) |
| **API gaps** | No ProjectMembership CRUD, no user list, no service account API, no user type editing |
| **Permissions** | `HasProjectMembership` enforced on project-scoped endpoints; `IsHumanUser` on profile/identity endpoints |
| **Web frontend** | Nothing — no profile page, no admin panel. Sidebar has a "Settings" link pointing to `#` |
| **MCP server** | Zero user management tools. No lock usage despite the AgentLock model existing |
| **CLI** | Zero user management commands. Only workplan/task/agent/import/config (`cli/vtf/commands/`) |

### Coverage Matrix

| Feature | Backend API | Web UI | MCP Tool | CLI Command |
|---------|------------|--------|----------|-------------|
| Token validation | `GET /v1/auth/validate/` | -- | -- | -- |
| Recent access | `GET /v1/profile/recent/` | Home page widget | -- | -- |
| Session history | `GET /v1/profile/sessions/` | -- | -- | -- |
| External identities | CRUD `/v1/external-identities/` | -- | -- | -- |
| Agent locks | CRUD `/v1/locks/` | -- | -- | -- |
| Channel mappings | CRUD `/v1/channel-mappings/` | -- | -- | -- |
| Project memberships | Model + permission check only | -- | -- | -- |
| User list | -- | -- | -- | -- |
| Service accounts | `create_service_account` mgmt cmd | -- | -- | -- |
| User type editing | -- | -- | -- | -- |

### User Personas

1. **Human user** — logs in via browser, works with projects and tasks, needs to see their own profile, sessions, and linked accounts
2. **Staff/admin** — manages users, memberships, locks, channel mappings, and service accounts across the platform (web + CLI)
3. **Agent** — API-only via MCP tools, needs to acquire locks, resolve channels, check permissions, and identify itself
4. **Operator** — uses CLI for troubleshooting, auditing, and scripting (service account creation, lock cleanup, membership reports)

Note: personas 2 and 4 overlap — staff/admin may use the web or CLI depending on context. The distinction is interface, not role.

## Scope

This design covers all three interfaces (web, MCP, CLI) and the backend API gaps they require. The interfaces will be implemented independently but designed together to ensure consistent capabilities and naming.

### In Scope

- User profile page (web, self-service)
- Admin user management (web, staff-only)
- Project membership CRUD (API + all three interfaces)
- Agent lock management (all three interfaces)
- Channel mapping management (web + CLI, admin)
- MCP tools for agent-relevant operations
- CLI commands for operator workflows
- Missing API endpoints to support the above

### Out of Scope

- OAuth/social login flows (separate research doc exists)
- Role-based UI differences beyond staff/non-staff
- User registration (admin-created only for now)
- Password reset flow

## Architecture

### Integration Patterns

The three interfaces integrate with the backend at different layers:

```
                        ┌──────────────┐
                        │   Service    │
                        │   Layer      │
                        │  (prefs/     │
                        │  services.py)│
                        └──────┬───────┘
                               │ direct call
              ┌────────────────┼────────────────┐
              │                │                 │
     ┌────────▼───────┐  ┌────▼──────┐  ┌──────▼─────────┐
     │  REST Views     │  │   MCP     │  │  Management    │
     │  (prefs/views)  │  │   Tools   │  │  Commands      │
     └────────┬────────┘  └───────────┘  └────────────────┘
              │ HTTP/JSON
     ┌────────┼────────┐
     │                  │
┌────▼─────┐     ┌─────▼────┐
│  Web UI  │     │   CLI    │
│  (React) │     │  (Click) │
└──────────┘     └──────────┘
```

| Interface | Transport | Auth | Data access |
|-----------|-----------|------|-------------|
| **Web** | HTTP (fetch) | Session cookie + CSRF | REST API |
| **CLI** | HTTP (requests via `VTFClient`) | Token header from `~/.vtf/config.yaml` | REST API |
| **MCP** | Same process | Token from `VTF_TOKEN` env var, validated via ORM | Django ORM via service layer |

### Where Code Is Shared

**MCP tools and REST views** both call the same service functions in `src/prefs/services.py`. This is the primary reuse point. When adding a new capability (e.g., membership CRUD), the implementation order is:

1. **Service function** in `prefs/services.py` — business logic, validation, ORM queries
2. **REST view** in `prefs/views.py` — thin DRF wrapper exposing the service over HTTP (consumed by web + CLI)
3. **MCP tool** in `mcp_server/tools/` — thin wrapper calling the service directly (consumed by agents)

The CLI shares no code with MCP or the REST views — it's a separate Python package (`cli/vtf/`) that makes HTTP calls via its own `VTFClient` class. But because CLI and web both consume the same REST API, adding an endpoint automatically serves both.

Today `prefs/services.py` has only three functions (`get_or_create_profile`, `record_access`, `create_service_account`). The views contain inline business logic (e.g., lock acquire/reconnect/conflict in `LockView.post`). As part of this work, that logic should be extracted into service functions so MCP tools can reuse it without duplicating the logic.

### What Each Interface Needs

Not every interface needs every feature. The matrix below maps features to interfaces based on persona needs:

| Feature | Web (user) | Web (admin) | MCP (agent) | CLI (operator) |
|---------|-----------|-------------|-------------|----------------|
| View own profile | Yes | Yes | Yes | Yes |
| View session history | Yes | -- | -- | Yes |
| Manage own external identities | Yes | -- | -- | -- |
| List all users | -- | Yes | -- | Yes |
| Manage project memberships | -- | Yes | Yes (read) | Yes |
| View/release agent locks | -- | Yes | Yes | Yes |
| Manage channel mappings | -- | Yes | Yes | Yes |
| Create service accounts | -- | Yes | -- | Yes |
| Resolve channel to project | -- | -- | Yes | -- |
| Acquire/reconnect lock | -- | -- | Yes | -- |
| Check own permissions | -- | -- | Yes | -- |

### API Gaps to Fill

These endpoints don't exist yet and must be built before the interfaces can consume them:

| Endpoint | Purpose | Required by |
|----------|---------|-------------|
| `GET /v1/users/` | List users with profile info (staff only) | Web admin, CLI |
| `GET /v1/users/<id>/` | User detail with memberships (staff only) | Web admin, CLI |
| `PATCH /v1/users/<id>/` | Update user type (staff only) | Web admin |
| `GET /v1/projects/<id>/members/` | List project members | Web admin, CLI, MCP |
| `POST /v1/projects/<id>/members/` | Add member with role | Web admin, CLI |
| `PATCH /v1/projects/<id>/members/<id>/` | Change member role | Web admin, CLI |
| `DELETE /v1/projects/<id>/members/<id>/` | Remove member | Web admin, CLI |
| `POST /v1/service-accounts/` | Create service account, return token (staff only) | Web admin, CLI |

Note: The membership endpoints nest under projects (`/v1/projects/<id>/members/`) following the existing pattern where workplans and backlog are nested under projects (`/v1/projects/<id>/workplans/`, `/v1/projects/<id>/backlog/`).

### Existing Endpoints — Permission Fixes

Several existing endpoints have permissions that are too broad:

| Endpoint | Current permission | Should be |
|----------|-------------------|-----------|
| `POST /v1/locks/` | `IsAuthenticated` | Agents + staff only (humans don't acquire locks) |
| `DELETE /v1/locks/<pk>/` | `IsAuthenticated` (owner only) | Owner OR staff (admin force-release) |
| `POST /v1/channel-mappings/` | `IsAuthenticated` | Staff only |
| `DELETE /v1/channel-mappings/<pk>/` | `IsAuthenticated` | Staff only |
| `GET /v1/channel-mappings/` | `IsAuthenticated` | `IsAuthenticated` (keep — agents need read access for resolution) |

### Service Layer Extractions

Business logic currently inline in views that should move to `prefs/services.py`:

| Logic | Current location | Service function |
|-------|-----------------|------------------|
| Lock acquire/reconnect/conflict | `LockView.post()` | `acquire_lock(user, project_id, role)` |
| Lock release | `LockDetailView.delete()` | `release_lock(lock_id, user, force=False)` |
| Channel mapping CRUD | `ChannelMappingView` | `create_channel_mapping()`, `list_channel_mappings()` |
| External identity CRUD | `ExternalIdentityView` | `link_identity()`, `list_identities()`, `unlink_identity()` |

## Implementation Order

The interfaces share a dependency on the service layer and API endpoints, so the natural order is:

1. **Backend gaps** — extract service functions from views, build missing REST endpoints (users, memberships, service accounts), fix permissions. All tests.
2. **MCP tools** — agent-relevant tools (lock acquire/release/list, channel resolve, identity lookup, member list, whoami). Thin wrappers over service functions.
3. **CLI commands** — operator workflows (`vtf user list`, `vtf lock list/release`, `vtf member list/add/remove`, `vtf service-account create`). HTTP calls to REST endpoints.
4. **Web UI** — profile page (self-service), admin settings panel (staff). Most effort (React components, routing, state management).

Each phase is independently shippable and testable. The backend gaps must come first since all three interfaces depend on them.

---

## Testing Strategy

### TDD Enforcement

Every phase follows strict RED-GREEN-REFACTOR:

1. **RED** — Write a failing test that describes the expected behavior
2. **GREEN** — Write the minimum code to make the test pass
3. **REFACTOR** — Clean up without changing behavior, tests stay green

No production code is written without a failing test first. This applies to:
- Service functions (unit tests)
- REST endpoints (API tests via `APIClient`)
- MCP tools (unit tests calling tool functions directly + E2E via `McpTestClient`)
- CLI commands (Click `CliRunner` + `requests_mock`)
- Web components (Vitest + React Testing Library)

### Test Layers

The project has three test layers, each with a specific role:

| Layer | Tool | Scope | When to run |
|-------|------|-------|-------------|
| **Unit** | `pytest` (backend), `vitest` (frontend) | Single function/component in isolation | During development, every commit |
| **Integration** | `pytest` with `APIClient` / `CliRunner` | Endpoint-to-database round trips, CLI-to-mock-API | During development, every commit |
| **E2E** | `pytest` against `docker-compose.e2e.yml` | Full stack (API + MCP + DB), real HTTP, real auth | Before declaring phase done |

The E2E stack (`docker-compose.e2e.yml`) runs API on port 18000 and MCP on port 18002, with a seeded database (`tests/e2e/seed.py`). E2E tests use `RestTestClient` and `McpTestClient` from `tests/e2e/`.

### E2E Coverage per Phase

Each phase must include E2E tests that prove the feature works from the consumer's perspective:

| Phase | E2E test file | What it proves |
|-------|--------------|----------------|
| 1. Backend | `tests/e2e/test_user_management.py` | REST endpoints work with real auth, real DB, correct permissions (staff vs non-staff vs agent) |
| 2. MCP | `tests/e2e/test_user_management.py` (extended) | MCP tools return correct data, respect auth, handle errors |
| 3. CLI | `cli/tests/test_user_commands.py` | CLI commands format output correctly, handle errors (uses `requests_mock`, not E2E stack) |
| 4. Web | `web/src/pages/__tests__/*.test.tsx` | Components render data, handle loading/error states, staff-only guards work |

Note: CLI tests use `requests_mock` (not the E2E stack) because the CLI is a thin HTTP client — its correctness depends on calling the right endpoints with the right params, not on the database. The E2E stack already verifies the endpoints work. Web tests similarly mock API responses since the React components are consumers, not the system under test.

### Regression Gate

Before any phase is declared done, the full existing test suite must pass with zero regressions:

```bash
# Backend (unit + integration)
docker compose exec api pytest

# Frontend
cd web && npx vitest run

# CLI
cd cli && pytest tests/

# E2E (requires stack up)
docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
pytest tests/e2e/
```

---

## Definition of Done

### Phase 1: Backend Gaps

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | All service functions extracted and unit-tested | `pytest tests/prefs/test_services.py` — each function has tests for happy path, edge cases, and error conditions |
| 2 | Views refactored to call services (no inline business logic) | Code review: views are thin wrappers with no ORM queries beyond `serializer.save()` |
| 3 | New REST endpoints functional | `pytest tests/prefs/test_user_list_api.py tests/prefs/test_membership_api.py tests/prefs/test_service_account_api.py` — CRUD + permission checks |
| 4 | Permission fixes applied | `pytest tests/prefs/test_lock_permissions.py tests/prefs/test_channel_mapping_permissions.py` — agents can acquire locks, humans cannot; only staff can write channel mappings |
| 5 | Zero regression | `docker compose exec api pytest` — full suite passes, existing test count unchanged or increased |
| 6 | E2E on live stack | `pytest tests/e2e/test_user_management.py` — staff can list users, add members, create service accounts; non-staff gets 403; agents get correct identity from validate endpoint |
| 7 | Seed data updated | `tests/e2e/seed.py` creates test users (human, agent, service), memberships, and a channel mapping for E2E |
| 8 | Test count | Minimum 40 new tests |

### Phase 2: MCP Tools

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | All 5 tools registered and callable | `pytest tests/mcp_server/test_identity_tools.py` — each tool returns `success_response` with correct data |
| 2 | Tools call service layer (not ORM directly) | Code review: tools import from `prefs.services`, not from `prefs.models` |
| 3 | Error cases handled | Tests cover: missing project context, lock conflict, channel not found, permission denied |
| 4 | E2E smoke updated | `tests/e2e/test_e2e_smoke.py` `EXPECTED_TOOLS` list includes the 5 new tools |
| 5 | E2E scenario test | `tests/e2e/test_user_management.py` extended: MCP client can call `vtf_whoami`, acquire and release a lock, resolve a channel |
| 6 | Zero regression | `docker compose exec api pytest` + `pytest tests/e2e/` — all pass |
| 7 | Test count | Minimum 15 new tests |

### Phase 3: CLI Commands

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | All commands executable | `vtf user list`, `vtf member list <pid>`, `vtf lock list`, `vtf channel-mapping list`, `vtf service-account create <name>` — each runs without error against the dev or dogfood instance |
| 2 | Unit tests with mocked HTTP | `cd cli && pytest tests/test_user_commands.py` — each subcommand tested with `requests_mock` for happy path and error cases |
| 3 | Output formatting correct | Tests assert tabular output format, column alignment, human-readable values |
| 4 | Error handling | Tests for 403 (not staff), 404 (not found), 409 (conflict) — CLI prints readable error, exits with code 1 |
| 5 | Commands registered | `vtf --help` shows the new command groups |
| 6 | Manual smoke test on dogfood | Run each command against `http://localhost:8001` with admin token, verify output matches expected data |
| 7 | Zero regression | `cd cli && pytest tests/` — all existing CLI tests pass |
| 8 | Test count | Minimum 20 new tests |

### Phase 4: Web UI

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | Routes accessible | Navigate to `/settings/profile`, `/settings/identities`, `/settings/sessions`, `/admin/users`, `/admin/locks`, `/admin/channel-mappings` — each renders without error |
| 2 | AuthContext enriched | `useAuth()` returns `isStaff`, `userType`, `projects` in addition to existing fields |
| 3 | Sidebar updated | Settings link works; admin links visible for staff, hidden for non-staff |
| 4 | Self-service pages functional | Profile shows identity + memberships; identities page can link/unlink; sessions page shows history with project filter |
| 5 | Admin pages functional | User list with search + type filter; user detail with editable user_type; locks with force-release; channel mappings with create/delete; service account creation shows token once |
| 6 | Staff-only guard | Non-staff navigating to `/admin/*` redirected to `/` |
| 7 | Component tests | `cd web && npx vitest run` — new tests for profile, admin users, admin locks, sidebar admin visibility |
| 8 | Visual verification on dogfood | Pages render correctly against real data on `http://localhost:8001`, no console errors |
| 9 | Zero regression | `cd web && npx vitest run` — all existing frontend tests pass |
| 10 | Test count | Minimum 15 new tests |

---

## Phase 1: Backend Gaps

### 1.1 Service Layer Extractions

Extract inline business logic from views into `src/prefs/services.py` so that both REST views and MCP tools can call the same functions.

#### Lock Services

```python
# prefs/services.py

class LockConflict(Exception):
    """Raised when a lock is held by another user."""
    def __init__(self, lock):
        self.lock = lock

def acquire_lock(user, project_id, role, session_id=""):
    """Acquire a lock, reconnect if same user, raise LockConflict if held by another.
    Returns the AgentLock instance."""

def release_lock(lock_id, user, force=False):
    """Release a lock. If force=True, staff can release any lock.
    Raises AgentLock.DoesNotExist or PermissionError."""

def list_locks(project_id=None):
    """List locks, optionally filtered by project."""
```

The current `LockView.post()` has three code paths (create, reconnect, conflict) — all move to `acquire_lock()`. The view becomes a thin wrapper that catches `LockConflict` and returns 409.

#### Channel Mapping Services

```python
def create_channel_mapping(provider, channel_id, project_id, channel_name=""):
    """Create a mapping. Returns the ChannelProjectMapping instance."""

def resolve_channel(provider, channel_id):
    """Look up the project_id for a channel. Returns project_id or None."""

def list_channel_mappings(provider=None, channel_id=None):
    """List mappings with optional filters."""

def delete_channel_mapping(mapping_id):
    """Delete a mapping by ID. Raises DoesNotExist."""
```

#### Identity Services

```python
def link_identity(user, provider, external_id, workspace_id=""):
    """Link an external identity to a user. Returns ExternalIdentity instance."""

def list_identities(user, provider=None):
    """List a user's external identities, optionally filtered by provider."""

def unlink_identity(identity_id, user):
    """Remove a linked identity. Raises DoesNotExist if not found or not owned."""
```

#### Membership Services

```python
def list_members(project_id):
    """List all members of a project with their roles."""

def add_member(project_id, user_id, role="member"):
    """Add a user to a project. Returns ProjectMembership instance.
    Raises IntegrityError if already a member."""

def update_member_role(membership_id, role):
    """Change a member's role. Returns updated ProjectMembership."""

def remove_member(membership_id):
    """Remove a member. Raises DoesNotExist."""

def check_membership(user, project_id):
    """Check if user has membership. Returns (has_access, role) tuple.
    Staff always returns (True, 'staff')."""
```

#### User Services

```python
def list_users(search=None, user_type=None):
    """List users with their profiles. Staff only.
    Supports search by username and filter by user_type."""

def get_user_detail(user_id):
    """Get a user with profile and memberships. Staff only."""

def update_user_type(user_id, user_type):
    """Change a user's type (human, agent, service). Staff only."""
```

### 1.2 New REST Endpoints

#### User List and Detail (staff only)

```
GET  /v1/users/                  → list users with profile info
GET  /v1/users/<id>/             → user detail with memberships
PATCH /v1/users/<id>/            → update user_type
```

**File**: `src/prefs/views.py` (or new `src/prefs/user_views.py` if views.py grows too large)

**URL registration**: `src/vtaskforge/urls.py`

```python
path('v1/users/', UserListView.as_view(), name='user-list'),
path('v1/users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
```

**Serializer**:
```python
class UserListSerializer(serializers.ModelSerializer):
    user_type = serializers.CharField(source='profile.user_type', read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'is_staff', 'is_active', 'user_type', 'date_joined', 'last_login']

class UserDetailSerializer(UserListSerializer):
    memberships = ProjectMembershipSerializer(source='project_memberships', many=True, read_only=True)
    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + ['memberships']
```

**Permissions**: `IsAuthenticated, IsAdminUser`

**Query params**: `?search=<username>&user_type=human|agent|service`

#### Project Members (nested under project)

```
GET    /v1/projects/<project_id>/members/          → list members
POST   /v1/projects/<project_id>/members/          → add member
PATCH  /v1/projects/<project_id>/members/<id>/     → change role
DELETE /v1/projects/<project_id>/members/<id>/      → remove member
```

**File**: `src/projects/views.py` (alongside existing `ProjectWorkplansView`, `ProjectBacklogView`)

**URL registration**: `src/projects/urls.py`

```python
path('projects/<str:project_id>/members/', ProjectMemberView.as_view(), name='project-members'),
path('projects/<str:project_id>/members/<int:pk>/', ProjectMemberDetailView.as_view(), name='project-member-detail'),
```

**Serializer**:
```python
class ProjectMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    class Meta:
        model = ProjectMembership
        fields = ['id', 'user_id', 'username', 'role', 'created_at']
```

**Permissions**:
- GET: `IsAuthenticated` + `HasProjectMembership` (members can see other members)
- POST/PATCH/DELETE: `IsAuthenticated` + `IsAdminUser` (only staff can modify)

**POST body**: `{ "username": "alice", "role": "member" }` — accepts username, not user ID, for usability.

#### Service Account Creation (staff only)

```
POST /v1/service-accounts/     → create service account, return user + token
```

**File**: `src/prefs/views.py`

**URL registration**: `src/vtaskforge/urls.py`

```python
path('v1/service-accounts/', ServiceAccountView.as_view(), name='service-accounts'),
```

**Request**: `{ "name": "ci-bot" }`

**Response**: `{ "id": 42, "username": "ci-bot", "token": "abc123...", "user_type": "service" }`

**Permissions**: `IsAuthenticated, IsAdminUser`

**Note**: The token is only returned on creation — it cannot be retrieved later. This matches the existing agent registration pattern.

### 1.3 Permission Fixes

Changes to existing views in `src/prefs/views.py`:

**LockView**:
- `POST`: Add `IsAgentOrStaff` permission (new permission class). Regular human users should not acquire locks.
- `DELETE`: Allow owner OR staff. Change from `lock = AgentLock.objects.get(pk=pk, user=request.user)` to also accept `request.user.is_staff`.

**ChannelMappingView**:
- `POST`: Add `IsAdminUser` permission.
- `DELETE`: Add `IsAdminUser` permission.
- `GET`: Keep `IsAuthenticated` (agents need read access for resolution).

New permission class:
```python
class IsAgentOrStaff(BasePermission):
    """Allow agent users (no usable password) and staff."""
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        return not request.user.has_usable_password()  # agent user
```

### 1.4 Tests

All new endpoints and service functions need tests. Following the existing pattern in `tests/prefs/`:

| Test file | What it covers |
|-----------|---------------|
| `tests/prefs/test_user_list_api.py` | User list/detail/update (staff only, search, filters) |
| `tests/prefs/test_membership_api.py` | Membership CRUD under projects (add, role change, remove, permission checks) |
| `tests/prefs/test_service_account_api.py` | Service account creation (token returned, user_type=service) |
| `tests/prefs/test_lock_permissions.py` | Lock acquire restricted to agents+staff, force-release by staff |
| `tests/prefs/test_channel_mapping_permissions.py` | Channel mapping write restricted to staff |
| `tests/prefs/test_services.py` | Unit tests for extracted service functions |

Expected: ~40-50 new tests.

---

## Phase 2: MCP Tools

New file: `src/mcp_server/tools/identity.py`

All tools follow the existing pattern: `@mcp.tool()` decorator, return `json.dumps(success_response(...))` or `json.dumps(error_response(...))`, import service functions directly.

### vtf_whoami

```python
@mcp.tool()
def vtf_whoami() -> str:
    """Return the current user's identity: username, user type, staff status, and project memberships.

    Use this to understand who you are and what projects you have access to.
    """
```

Calls: `get_or_create_profile()`, `ProjectMembership.objects.filter(user=...)`.

Returns: `{ user_id, username, user_type, is_staff, projects: [{project_id, role}] }`

Available actions: `["vtf_get_context", "vtf_manage_lock"]`

### vtf_manage_lock

```python
@mcp.tool()
def vtf_manage_lock(
    action: str,
    project_id: str = "",
    role: str = "",
    lock_id: int = 0,
) -> str:
    """Manage agent session locks.

    Actions:
      - list: List all active locks (optionally filter by project_id)
      - acquire: Acquire a lock for a project+role (reconnects if already held by you)
      - release: Release a lock by lock_id

    Locks prevent duplicate agent sessions. Acquire a lock before starting work
    on a project in a specific role (e.g., architect, executor).
    """
```

Calls: `acquire_lock()`, `release_lock()`, `list_locks()` from services.

### vtf_resolve_channel

```python
@mcp.tool()
def vtf_resolve_channel(
    provider: str,
    channel_id: str,
) -> str:
    """Resolve an external channel (Slack, etc.) to a vtf project.

    Returns the project_id mapped to this channel, or an error if no mapping exists.
    Use this when you receive a message from an external channel and need to know
    which project context to use.
    """
```

Calls: `resolve_channel()` from services.

### vtf_list_members

```python
@mcp.tool()
def vtf_list_members(project_id: str = "") -> str:
    """List members of a project with their roles.

    If project_id is omitted, uses the session's default project.
    Returns usernames and roles (owner, member, viewer).
    """
```

Calls: `list_members()` from services.

### vtf_manage_channel_mapping

```python
@mcp.tool()
def vtf_manage_channel_mapping(
    action: str,
    provider: str = "",
    channel_id: str = "",
    channel_name: str = "",
    project_id: str = "",
    mapping_id: int = 0,
) -> str:
    """Manage channel-to-project mappings (staff/admin only).

    Actions:
      - list: List all mappings (optionally filter by provider)
      - create: Create a new mapping (requires provider, channel_id, project_id)
      - delete: Remove a mapping by mapping_id
    """
```

Calls: `create_channel_mapping()`, `list_channel_mappings()`, `delete_channel_mapping()`.

### Tool Registration

Register tools in `src/mcp_server/tools/__init__.py` (or wherever existing tools are loaded).

Expected: 5 new MCP tools, ~15 tests in `tests/mcp_server/test_identity_tools.py`.

---

## Phase 3: CLI Commands

New file: `cli/vtf/commands/user.py`

All commands follow the existing Click pattern: `@click.group()` for the group, `@group.command()` for subcommands, `VTFClient` for HTTP calls, `click.echo()` for output.

### vtf user

```
vtf user list [--type human|agent|service] [--search NAME]
vtf user show <id>
```

**list** — Tabular output: `ID  USERNAME  TYPE  STAFF  LAST_LOGIN`
**show** — Detail view with memberships:
```
Username:  alice
Type:      human
Staff:     yes
Joined:    2026-01-15
Projects:
  my-project  owner
  other-proj  member
```

Calls: `GET /v1/users/`, `GET /v1/users/<id>/`

### vtf member

```
vtf member list <project-id>
vtf member add <project-id> <username> [--role member|viewer|owner]
vtf member set-role <project-id> <membership-id> <role>
vtf member remove <project-id> <membership-id>
```

**list** — Tabular output: `ID  USERNAME  ROLE  SINCE`

Calls: `/v1/projects/<id>/members/` endpoints.

### vtf lock

```
vtf lock list [--project PROJECT_ID]
vtf lock release <lock-id> [--force]
```

**list** — Tabular output: `ID  PROJECT  ROLE  HELD_BY  SINCE  LAST_ACTIVITY`
**release** — Releases a lock. `--force` requires staff token.

Calls: `GET /v1/locks/`, `DELETE /v1/locks/<id>/`

### vtf channel-mapping

```
vtf channel-mapping list [--provider PROVIDER]
vtf channel-mapping create --provider PROVIDER --channel-id ID --project PROJECT_ID [--channel-name NAME]
vtf channel-mapping delete <id>
```

Calls: `/v1/channel-mappings/` endpoints.

### vtf service-account

```
vtf service-account create <name>
```

Output:
```
Created service account: ci-bot
Token: abc123def456...
⚠ Save this token — it cannot be retrieved later.
```

Calls: `POST /v1/service-accounts/`

### Command Registration

Add to `cli/vtf/commands/__init__.py` (or wherever the Click group aggregates subcommands).

Expected: 5 command groups, ~12 subcommands, ~20 tests in `cli/tests/test_user_commands.py`.

---

## Phase 4: Web UI

### 4.0 Visual Design Decisions

Mockups generated via Stitch (project: `VTaskForge User Management UI`, ID: `2156115794839229768`).

**Design system** (matches existing vtf UI):
- MD3 color tokens: primary `#004cc9`, tertiary `#006443`, error `#ba1a1a`
- Surfaces: `#f7f9fb` background, `#ffffff` cards with `rounded-xl shadow-[0_12px_40px_rgba(25,28,30,0.04)]`
- Fonts: Manrope (headlines, bold), Inter (body, labels)
- Labels: `text-[10px] uppercase tracking-widest font-bold text-on-surface-variant`
- Icons: Google Material Symbols Outlined
- Components: existing `NavLink`, `StatCard`, `Skeleton` patterns from Home page

**User type badge colors** (consistent across all pages):
- `human` — `bg-blue-100 text-blue-700`
- `agent` — `bg-purple-100 text-purple-700`
- `service` — `bg-amber-100 text-amber-700`

**Role badge colors** (membership roles):
- `owner` — `bg-primary text-on-primary` (solid blue)
- `member` — `bg-surface-container-high text-on-surface`
- `viewer` — `bg-surface-container text-on-surface-variant`

**Sidebar changes**:
- Settings link becomes real (`/settings/profile`), uses existing `NavLink` style
- Admin section appears below Settings for staff users only, with a `text-[10px] uppercase` "Admin" section header (same style as "Navigation" header)
- Admin items: `person` (Users), `lock` (Locks), `cable` (Channels) — Material Symbols

**Page layout**:
- Profile page: card-based layout (identity card + memberships card + linked accounts card)
- Admin pages: header row (title + filters) + single white card containing data table
- All pages use `pt-8 px-8 pb-12` content padding (same as Home)
- No decorative banners, no dashboard widgets — clean and data-focused

### 4.1 Routes

Add to `web/src/App.tsx`:

```tsx
<Route path="/settings" element={<Settings />} />
<Route path="/settings/profile" element={<ProfilePage />} />
<Route path="/settings/identities" element={<IdentitiesPage />} />
<Route path="/settings/sessions" element={<SessionsPage />} />
<Route path="/admin/users" element={<AdminUsersPage />} />
<Route path="/admin/users/:id" element={<AdminUserDetailPage />} />
<Route path="/admin/locks" element={<AdminLocksPage />} />
<Route path="/admin/channel-mappings" element={<AdminChannelMappingsPage />} />
<Route path="/admin/service-accounts" element={<AdminServiceAccountsPage />} />
```

The `/settings/*` routes are self-service (any authenticated human). The `/admin/*` routes check `is_staff` and redirect non-staff to `/`.

### 4.2 Sidebar Update

The existing Settings link (`<Link to="#">`) becomes a real link to `/settings`. For staff users, add an "Admin" section below Settings.

```
Sidebar (bottom section):
  ┌─────────────────────┐
  │ ⚙ Settings          │  → /settings
  │                     │
  │ [staff only:]       │
  │ 👤 Users            │  → /admin/users
  │ 🔒 Locks            │  → /admin/locks
  │ 📡 Channels         │  → /admin/channel-mappings
  └─────────────────────┘
```

The sidebar needs the current user's `is_staff` flag. This comes from `GET /v1/auth/validate/` (already exists, returns `is_staff`). Add a `useCurrentUser()` hook that calls this endpoint once on app load and caches it.

### 4.3 API Hooks

New file: `web/src/api/users.ts`

```typescript
// Self-service
useCurrentUser()           → GET /v1/auth/validate/
useSessionHistory()        → GET /v1/profile/sessions/
useExternalIdentities()    → GET /v1/external-identities/
useLinkIdentity()          → POST /v1/external-identities/
useUnlinkIdentity()        → DELETE /v1/external-identities/<id>/

// Admin
useUsers(search?, type?)   → GET /v1/users/
useUserDetail(id)          → GET /v1/users/<id>/
useUpdateUserType()        → PATCH /v1/users/<id>/
useProjectMembers(pid)     → GET /v1/projects/<id>/members/
useAddMember()             → POST /v1/projects/<id>/members/
useRemoveMember()          → DELETE /v1/projects/<id>/members/<id>/
useLocks(projectId?)       → GET /v1/locks/
useReleaseLock()           → DELETE /v1/locks/<id>/
useChannelMappings()       → GET /v1/channel-mappings/
useCreateMapping()         → POST /v1/channel-mappings/
useDeleteMapping()         → DELETE /v1/channel-mappings/<id>/
useCreateServiceAccount()  → POST /v1/service-accounts/
```

All hooks use TanStack Query (`useQuery` for reads, `useMutation` for writes) following the existing pattern in `web/src/api/`.

### 4.4 Pages

#### Settings (landing)

`/settings` — simple hub linking to profile, identities, sessions. Could be a redirect to `/settings/profile` if there's nothing to show on the landing.

#### Profile Page

`/settings/profile` — read-only view of the current user's identity.

```
┌──────────────────────────────────────┐
│  Profile                             │
├──────────────────────────────────────┤
│  Username:    jasonvi                │
│  Type:        human                  │
│  Staff:       Yes                    │
│  Member since: 2026-01-15            │
│                                      │
│  Projects                            │
│  ┌──────────────┬────────┐           │
│  │ Project      │ Role   │           │
│  ├──────────────┼────────┤           │
│  │ viloforge    │ owner  │           │
│  │ vtaskforge   │ member │           │
│  └──────────────┴────────┘           │
└──────────────────────────────────────┘
```

Data source: `useCurrentUser()` (validate endpoint).

#### External Identities Page

`/settings/identities` — manage linked external accounts.

```
┌──────────────────────────────────────────┐
│  Linked Accounts                         │
├──────────────────────────────────────────┤
│  ┌────────┬──────────────┬────────────┐  │
│  │Provider│ External ID  │            │  │
│  ├────────┼──────────────┼────────────┤  │
│  │ slack  │ U01234ABCDE  │ [Unlink]   │  │
│  │ github │ jasonvi      │ [Unlink]   │  │
│  └────────┴──────────────┴────────────┘  │
│                                          │
│  [+ Link Account]                        │
│  Provider: [________]                    │
│  External ID: [________]                 │
│  Workspace ID: [________] (optional)     │
│  [Save]                                  │
└──────────────────────────────────────────┘
```

#### Session History Page

`/settings/sessions` — read-only list of agent sessions.

```
┌──────────────────────────────────────────────────────┐
│  Session History                                     │
├──────────────────────────────────────────────────────┤
│  ┌─────────┬──────────┬────────┬───────────────────┐ │
│  │ Project │ Role     │Channel │ Started            │ │
│  ├─────────┼──────────┼────────┼───────────────────┤ │
│  │ vilofrg │architect │ slack  │ 2026-04-01 14:30  │ │
│  │ vilofrg │executor  │ cli    │ 2026-04-01 10:15  │ │
│  └─────────┴──────────┴────────┴───────────────────┘ │
│                                                      │
│  Filter: [Project ▼]                                 │
└──────────────────────────────────────────────────────┘
```

#### Admin: Users Page

`/admin/users` — staff-only user management.

```
┌──────────────────────────────────────────────────────┐
│  Users                          [Search: ________]   │
│                                 [Type: All ▼    ]    │
├──────────────────────────────────────────────────────┤
│  ┌────┬───────────┬─────────┬───────┬──────────────┐ │
│  │ ID │ Username  │ Type    │ Staff │ Last Login   │ │
│  ├────┼───────────┼─────────┼───────┼──────────────┤ │
│  │  1 │ admin     │ human   │ Yes   │ 2026-04-02   │ │
│  │  2 │ alice     │ human   │ No    │ 2026-04-01   │ │
│  │  5 │ agt-exec1 │ agent   │ No    │ --           │ │
│  │  8 │ ci-bot    │ service │ No    │ --           │ │
│  └────┴───────────┴─────────┴───────┴──────────────┘ │
│                                                      │
│  [+ Create Service Account]                          │
└──────────────────────────────────────────────────────┘
```

Clicking a row navigates to `/admin/users/<id>` (user detail with memberships, editable user_type).

#### Admin: Locks Page

`/admin/locks` — view and force-release stale agent locks.

```
┌────────────────────────────────────────────────────────┐
│  Agent Locks                    [Project: All ▼   ]    │
├────────────────────────────────────────────────────────┤
│  ┌──────────┬───────────┬──────────┬─────────┬───────┐ │
│  │ Project  │ Role      │ Held by  │ Since   │       │ │
│  ├──────────┼───────────┼──────────┼─────────┼───────┤ │
│  │ vilofrg  │ architect │ agt-arch │ 2h ago  │ [X]   │ │
│  │ vtf-dev  │ executor  │ agt-ex1  │ 45m ago │ [X]   │ │
│  └──────────┴───────────┴──────────┴─────────┴───────┘ │
│                                                        │
│  [X] = Force release (with confirmation dialog)        │
└────────────────────────────────────────────────────────┘
```

#### Admin: Channel Mappings Page

`/admin/channel-mappings` — manage channel-to-project mappings.

```
┌───────────────────────────────────────────────────────┐
│  Channel Mappings                                     │
├───────────────────────────────────────────────────────┤
│  ┌──────────┬──────────────┬──────────┬─────────────┐ │
│  │ Provider │ Channel      │ Project  │             │ │
│  ├──────────┼──────────────┼──────────┼─────────────┤ │
│  │ slack    │ #viloforge   │ vilofrg  │ [Delete]    │ │
│  │ slack    │ #vtf-dev     │ vtf-dev  │ [Delete]    │ │
│  └──────────┴──────────────┴──────────┴─────────────┘ │
│                                                       │
│  [+ Add Mapping]                                      │
│  Provider: [________]                                 │
│  Channel ID: [________]                               │
│  Channel Name: [________] (optional, display only)    │
│  Project: [________]                                  │
│  [Save]                                               │
└───────────────────────────────────────────────────────┘
```

### 4.5 AuthContext Enhancement

The current `AuthContext` only stores `{ authenticated, loading, username }`. It needs `is_staff` to conditionally render admin sidebar links and protect admin routes.

Change `AuthProvider` to call `GET /v1/auth/validate/` instead of `GET /v1/auth/login` on mount. The validate endpoint already returns `is_staff`, `user_type`, and `projects`. This replaces the simple login check with a richer identity load.

```typescript
interface AuthState {
  authenticated: boolean;
  loading: boolean;
  username: string;
  isStaff: boolean;
  userType: 'human' | 'agent' | 'service';
  projects: { project_id: string; role: string }[];
}
```

### 4.6 Tests

Frontend tests use Vitest + React Testing Library, following the existing pattern in `web/src/pages/__tests__/`.

| Test file | What it covers |
|-----------|---------------|
| `web/src/pages/__tests__/ProfilePage.test.tsx` | Renders profile data, shows project memberships |
| `web/src/pages/__tests__/AdminUsersPage.test.tsx` | User list, search, type filter, staff-only guard |
| `web/src/pages/__tests__/AdminLocksPage.test.tsx` | Lock list, force-release confirmation |
| `web/src/components/__tests__/Sidebar.admin.test.tsx` | Admin links visible for staff, hidden for non-staff |

Expected: ~15-20 frontend tests.

---

## Summary

| Phase | Files touched | New tests | E2E | Definition of Done |
|-------|--------------|-----------|-----|-------------------|
| 1. Backend gaps | `prefs/services.py`, `prefs/views.py`, `projects/views.py`, `projects/urls.py`, `vtaskforge/urls.py`, `tests/e2e/seed.py` | 40+ | REST endpoints on live stack | 8 criteria: services extracted, endpoints functional, permissions fixed, E2E passes, zero regression |
| 2. MCP tools | `mcp_server/tools/identity.py`, `mcp_server/tools/__init__.py` | 15+ | MCP tools on live stack | 7 criteria: tools registered, service layer calls, E2E smoke + scenario, zero regression |
| 3. CLI commands | `cli/vtf/commands/user.py`, `cli/vtf/commands/__init__.py` | 20+ | Manual on dogfood | 8 criteria: commands executable, mocked HTTP tests, output formatting, manual smoke on dogfood |
| 4. Web UI | `web/src/pages/` (6 new), `web/src/api/users.ts`, `web/src/App.tsx`, `web/src/components/Sidebar.tsx` | 15+ | Visual on dogfood | 10 criteria: routes accessible, auth enriched, sidebar updated, admin guard, visual verification |

Total: 90+ new tests across all phases.

### TDD Workflow Per Feature

Every feature within every phase follows this cycle:

```
1. Write failing test (RED)
2. Write minimum code (GREEN)
3. Refactor (keep tests green)
4. Run full suite (regression check)
5. Repeat for next feature
```

At phase end: run E2E, verify on dogfood, confirm all Definition of Done criteria met.
