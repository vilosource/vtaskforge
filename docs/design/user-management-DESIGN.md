# User Management & Identity — Design

## Problem

vtaskforge is growing from a standalone task tracker to the identity provider for the viloforge platform. Multiple services (vtf-kb, vafi, session routing bridge, channel adapters) need to authenticate users and agents against vtf. Today each service handles identity independently or not at all:

- vtf has Django's default User model with session + token auth, but no cross-service validation API
- Agent users are distinguished from humans by a convention (`has_usable_password() = False`), not a formal type
- No external identity mapping (Slack user ID → vtf user)
- No session tracking across agent interactions
- No project-level access control
- No persistent agent session locks (architect occupancy)
- `created_by` fields are plain strings, not FK to User — no verifiable audit trail

## Current State

### Authentication

| Method | How it works | Used by |
|--------|-------------|---------|
| Session cookie | Django session + CSRF | Browser (vtf frontend) |
| Token header | `Authorization: Token <40-char>` (DRF TokenAuth) | Agents, CLI, MCP servers |
| Auth code exchange | Single-use 64-char hex, 60s TTL | vafi-console bridge |

Both session and token auth are enabled on all endpoints via DRF `DEFAULT_AUTHENTICATION_CLASSES`.

### User Model

Django default `django.contrib.auth.models.User`. No custom user model. No AUTH_USER_MODEL override.

### Agent Registration

```python
# agents/views.py — on POST /v1/agents/
user = User.objects.create_user(username=agent.id)  # No password set
token = Token.objects.create(user=user)
# Agent users: has_usable_password() = False
```

### UserProfile (exists, from recently-accessed feature)

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Currently only used for the recently-accessed feature. No `user_type` field yet.

## Design

### Principle: vtf Is the Identity Provider

vtf already owns users, tokens, and sessions. Rather than building a separate identity service, vtf becomes the identity provider for all viloforge services:

- vtf owns users, tokens, sessions, and profiles
- Other services validate tokens by calling vtf's validation API
- Authorization decisions stay in vtf — other services delegate, not duplicate

### 7 Models

#### 1. UserProfile Enhancement — user_type

Formalize the agent vs human distinction:

```python
class UserProfile(models.Model):
    USER_TYPES = [
        ("human", "Human"),
        ("agent", "Agent"),
        ("service", "Service Account"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="human")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Auto-detected: `agent` if user has no usable password, `human` if they do, `service` if explicitly created as a service account.

#### 2. Token Validation API

New endpoint that other services call to authenticate tokens:

```
GET /v1/auth/validate/
Authorization: Token <key>

200 OK:
{
  "user_id": 42,
  "username": "admin",
  "user_type": "human",
  "is_staff": true,
  "projects": []
}

401 Unauthorized:
{ "error": "Invalid or expired token." }
```

Other services (vtf-kb, bridge) call this endpoint, cache the result for 60 seconds. Simple DB lookup on vtf's side — Token → User → UserProfile.

#### 3. ExternalIdentity

Maps external channel identities (Slack, WhatsApp, Telegram, mobile) to vtf users. Created via a one-time account linking flow.

```python
class ExternalIdentity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="external_identities")
    provider = models.CharField(max_length=30)
    # "slack", "whatsapp", "telegram", "mobile"
    external_id = models.CharField(max_length=255)
    # Slack user ID, phone number, Telegram user ID
    workspace_id = models.CharField(max_length=255, blank=True, default="")
    # Optional — Slack workspace for multi-workspace support
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id", "workspace_id"],
                name="unique_external_identity",
            ),
        ]
```

Linking flow:
1. User sends `/vtf link` in Slack (or first message in WhatsApp)
2. Bridge responds with a vtf auth URL: `vtf.viloforge.com/auth/external-link/?token=xyz&provider=slack&external_id=U12345`
3. User clicks, authenticates in vtf
4. vtf creates ExternalIdentity: `(slack, U12345) → vtf user admin`
5. All future messages from Slack `U12345` auto-resolve to vtf user `admin`

#### 4. AgentLock

Persistent agent sessions (architect, web designer) require a lock per project per role. Only one user can hold the lock at a time — prevents conflicting design decisions.

```python
class AgentLock(models.Model):
    project_id = models.CharField(max_length=50)
    role = models.CharField(max_length=30)
    # "architect", "web_designer", "schema_designer"
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_locks")
    session_id = models.CharField(max_length=255, blank=True, default="")
    # Pi/Claude session ID or cxdb context ID
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project_id", "role"],
                name="unique_project_role_lock",
            ),
        ]
```

Lock lifecycle:
- Acquire: `POST /v1/locks/` → 200 (or 409 if already locked by another user)
- Release: `DELETE /v1/locks/{id}/` → 200
- Auto-release: timeout after N hours of inactivity
- Reconnect: same user acquiring same lock → returns existing lock

#### 5. SessionRecord

Lightweight index of all agent sessions. Points to cxdb for full conversation traces. Enables "show me all my architect sessions this week" without querying cxdb directly.

```python
class SessionRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="session_records")
    project_id = models.CharField(max_length=50)
    role = models.CharField(max_length=30)
    # "architect", "assistant", "executor", "judge"
    cxdb_context_id = models.IntegerField(null=True, blank=True)
    channel = models.CharField(max_length=30, blank=True, default="")
    # "web", "slack", "mobile", "webhook"
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True, default="")
    # One-liner from NL summarizer

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["project_id", "-started_at"]),
        ]
```

#### 6. ChannelProjectMapping

Optional admin-configured mapping from external channels to projects. Enables: messages in Slack `#vtf-dev` auto-resolve to project "vtf" without the user specifying.

```python
class ChannelProjectMapping(models.Model):
    provider = models.CharField(max_length=30)
    channel_id = models.CharField(max_length=255)
    channel_name = models.CharField(max_length=255, blank=True, default="")
    # Display name for admin UI
    project_id = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "channel_id"],
                name="unique_channel_mapping",
            ),
        ]
```

#### 7. ProjectMembership

Links users to projects with roles. Advisory in the first phase (not enforced), enforced later.

```python
class ProjectMembership(models.Model):
    ROLES = [
        ("owner", "Owner"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_memberships")
    project_id = models.CharField(max_length=50)
    role = models.CharField(max_length=20, choices=ROLES, default="member")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project_id"],
                name="unique_user_project",
            ),
        ]
```

### Identity Flow Across Services

```
Human logs into vtf (session cookie)
  ├─→ vtf API: session auth, request.user available
  ├─→ vtf-kb API: same token → vtf-kb calls GET /v1/auth/validate/
  ├─→ vafi-console: session → auth code → console session
  └─→ Architect pod MCP: token in headers → validated by vtf

Agent registers with vtf (gets token)
  ├─→ vtf API: token auth
  └─→ vtf-kb API: same token → validated via /v1/auth/validate/

External channel (Slack, mobile):
  ├─→ Bridge resolves: provider + external_id → ExternalIdentity → vtf user
  └─→ Bridge passes vtf token to all downstream API calls

Service account (summarizer, auto-discovery):
  └─→ vtf-kb API: service token → validated as user_type=service
```

### Audit Trail

Every mutation records who did it via FK, not string:

```python
# On models that need it:
created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
```

For vtf-kb entries, the provenance tracks source (human/architect/summarizer) and the verified user identity.

## API Endpoints

### Existing (no changes needed)
- `POST /v1/auth/login` — session login
- `POST /v1/auth/logout` — session logout
- `POST /v1/auth/code/` — generate console auth code
- `POST /v1/auth/exchange/` — exchange code for user info

### New

| Endpoint | Method | Phase | Purpose |
|----------|--------|-------|---------|
| `/v1/auth/validate/` | GET | 1 | Token validation for cross-service auth |
| `/v1/auth/external-link/` | GET/POST | 2 | Account linking flow for external channels |
| `/v1/profile/sessions/` | GET | 2 | List user's session history |
| `/v1/external-identities/` | GET/POST/DELETE | 2 | Manage linked external accounts |
| `/v1/locks/` | GET/POST | 3 | List and acquire agent locks |
| `/v1/locks/{id}/` | DELETE | 3 | Release a lock |
| `/v1/channel-mappings/` | GET/POST/DELETE | 3 | Manage channel-to-project mappings |
| `/v1/project-memberships/` | GET/POST/PATCH/DELETE | 4 | Manage project memberships |

## Where Models Live

**Decision: All new models go in the `prefs` app.** It already exists with UserProfile and RecentAccess. One app, one migration sequence, less indirection. The app name is fine — "prefs" covers user preferences, identity, and activity. Don't rename it.

## URL Mounting

New endpoints mount at two prefixes:

| Prefix | Endpoints | Rationale |
|--------|-----------|-----------|
| `/v1/auth/` | `validate/`, `external-link/` | Auth concerns, alongside existing `login`, `logout`, `code/`, `exchange/` |
| `/v1/profile/` | `sessions/` | User-facing, alongside existing `recent/` |
| `/v1/` | `external-identities/`, `locks/`, `channel-mappings/`, `project-memberships/` | Resource endpoints at the API root |

The auth endpoints (`validate`, `external-link`) go in `vtaskforge/urls.py` directly (like the existing `login`/`logout`). The resource endpoints can use DRF routers.

## What This Enables

| Feature | Requires Phase |
|---------|---------------|
| vtf-kb shared auth | 1 (token validation) |
| Audit trail on knowledge entries | 1 (user identity in vtf-kb) |
| Agent vs human permission differences | 1 (user_type) |
| Slack/mobile/WhatsApp agent access | 2 (external identity) |
| "Show my sessions" history | 2 (session records) |
| Persistent architect sessions (lock) | 3 (agent locks) |
| Slack channel → project auto-resolution | 3 (channel mapping) |
| Project-scoped access control | 4 (project membership) |
| Summarizer writes to vtf-kb | 5 (service accounts) |
| Multi-team project isolation | 6 (access enforcement) |

## Existing Code Locations

The implementing agent needs to know where things are in the vtaskforge codebase:

| Component | File | Notes |
|-----------|------|-------|
| UserProfile model (exists) | `src/prefs/models.py` | Has user FK, created_at, updated_at. Needs user_type field. |
| RecentAccess model (exists) | `src/prefs/models.py` | Separate model, leave untouched. |
| prefs services (exists) | `src/prefs/services.py` | Has `record_access()`. Add profile services here. |
| prefs views (exists) | `src/prefs/views.py` | Has `RecentAccessView`. Add new views here. |
| prefs URLs (exists) | `src/prefs/urls.py` | Currently mounts at `/v1/profile/`. |
| prefs mixins (exists) | `src/prefs/mixins.py` | Has `TrackAccessMixin`. |
| prefs app config | `src/prefs/apps.py` | Registered in `INSTALLED_APPS` as `'prefs'`. |
| Auth code views | `src/core/views.py:161-211` | ConsoleCodeGenerateView, ConsoleCodeExchangeView. Pattern to follow. |
| Auth code model | `src/core/models.py:37-61` | ConsoleAuthCode. Pattern for single-use codes. |
| Agent registration | `src/agents/views.py` | Creates User + Token on POST /v1/agents/. |
| DRF auth config | `src/vtaskforge/settings/base.py` | REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES: TokenAuth + SessionAuth |
| URL mounting | `src/vtaskforge/urls.py` | prefs mounted at `path('v1/profile/', include('prefs.urls'))` |
| Test factories | `tests/factories.py` | ProjectFactory, TaskFactory, WorkplanFactory available. |
| Existing prefs tests | `tests/prefs/test_recent_access.py` | 17 tests for recently accessed. Follow this pattern. |

## Why Each Model Exists

For context if you're implementing without the research discussion:

| Model | Why it exists | What breaks without it |
|-------|-------------|----------------------|
| **UserProfile.user_type** | Agents and humans call the same APIs but should have different permissions. Today we use `has_usable_password()` as a hack. `user_type` makes it explicit, queryable, and extensible (service accounts). | vtf-kb can't distinguish who is calling. Profile endpoints can't reject agents. |
| **Token validation API** | vtf-kb, the session routing bridge, and future services need to authenticate tokens. They can't access vtf's database directly (separate service). The validation endpoint lets them verify tokens via HTTP. | No service can authenticate against vtf. vtf-kb is unbuilable. |
| **ExternalIdentity** | Users interact with agents from Slack, WhatsApp, mobile apps. Each channel has its own user ID (Slack: U12345, WhatsApp: +358...). This model maps channel identities to vtf users via a one-time linking flow. | No multi-channel access. Agents only work from the vtf web UI. |
| **AgentLock** | Persistent agent sessions (architect) need exclusive access per project — two users designing simultaneously creates conflicting decisions. The lock ensures one user owns the session at a time. | Multiple users corrupt each other's architect sessions. No session ownership. |
| **SessionRecord** | Every agent invocation should be traceable: who asked what, when, on which project, via which channel. Points to cxdb for full traces. Enables "show my sessions" and audit. | No session history. No audit trail. Can't answer "what did I ask the architect last week?" |
| **ChannelProjectMapping** | When a Slack message arrives in #vtf-dev, the system should auto-resolve it to the "vtf" project without asking the user. Admin configures these mappings. | Every Slack message requires explicit "on project X" — poor UX. |
| **ProjectMembership** | Not every user should access every project. Today all authenticated users see everything. Memberships enable project-level access control when needed. | No multi-team isolation. Fine for now, needed for growth. |

## Background: The Viloforge Platform

vtaskforge is one of four services in the viloforge platform:

- **vtf (vtaskforge)** — Task tracker + identity provider. Projects, workplans, tasks, state machine. This repo.
- **vtf-kb** — Knowledge service (facts, decisions, gotchas, patterns). Separate repo, not built yet. Will authenticate against vtf.
- **vafi** — Agent fleet (controller, executor, judge, architect pods). Separate repo. Already uses vtf tokens.
- **cxdb** — Trace store (agent conversation DAGs). Separate repo. Internal service, no auth.

vtf is the identity provider because it already owns users, tokens, sessions, and projects. The token validation API (`GET /v1/auth/validate/`) is how other services verify identity without accessing vtf's database directly.
