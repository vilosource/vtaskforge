# User Management — Implementation Plan

Design reference: `docs/design/user-management-DESIGN.md` — read this FIRST for full context on why each model exists, what the viloforge platform is, and existing code locations.

## Overview

6 phases, each independently deployable and valuable. TDD red/green for all code. E2E verification before declaring done. Each phase builds on the previous but can be paused without leaving the system in a broken state.

All changes are in the vtaskforge codebase. All new models go in the `prefs` app (already exists at `src/prefs/` with UserProfile + RecentAccess models).

## Conventions

- **Tests:** pytest + pytest-django. Test files in `tests/prefs/`. Use `@pytest.mark.django_db`. Use `APIClient` from `rest_framework.test`. Factories in `tests/factories.py`.
- **DB env:** `DATABASE_URL=postgres://vtf:vtfdev@localhost:5436/vtaskforge` (start DB: `docker compose up -d db`)
- **Run tests:** `DATABASE_URL=... python -m pytest tests/prefs/ -v`
- **Full regression:** `DATABASE_URL=... python -m pytest tests/ -q --tb=no` (expect ~1200+ passing)
- **Migrations:** `DATABASE_URL=... python src/manage.py makemigrations prefs && ... migrate prefs`
- **Build:** `docker build -f Dockerfile.prod -t harbor.viloforge.com/vafi/vtf:$(git rev-parse --short HEAD) .`
- **Deploy:** `kubectl set image deployment/vtf-api -n vtf-dev vtf-api=harbor.viloforge.com/vafi/vtf:<hash>` then run migration in pod
- **Image tags:** Always use git commit hash, NEVER `latest` or named tags
- **URL mounting:** prefs URLs currently at `path('v1/profile/', include('prefs.urls'))` in `src/vtaskforge/urls.py`. New auth endpoints mount at `path('v1/auth/...')`.

## Phase 1: Token Validation + User Type

**Prerequisite for: vtf-kb, session routing bridge, all future services.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/models.py` | Add `user_type` field to UserProfile |
| `prefs/services.py` | Add `get_or_create_profile()` with auto-detection |
| `prefs/views.py` | Add `TokenValidationView` |
| `prefs/urls.py` | Add `/validate/` route |
| `vtaskforge/urls.py` | Mount at `/v1/auth/validate/` |
| Migration | Add user_type field |

### TDD Steps

**Step 1: UserProfile.user_type (RED → GREEN)**

```python
# tests/prefs/test_user_type.py

def test_profile_user_type_defaults_to_human()
def test_profile_user_type_agent_for_no_password_user()
def test_profile_auto_created_on_first_access()
def test_existing_profiles_get_user_type_human()
```

Implement: add `user_type` CharField to UserProfile, add `get_or_create_profile(user)` that auto-detects type.

**Step 2: Validation endpoint (RED → GREEN)**

```python
# tests/prefs/test_token_validation.py

def test_validate_human_token_returns_correct_payload()
def test_validate_agent_token_returns_agent_type()
def test_validate_invalid_token_returns_401()
def test_validate_no_token_returns_401()
def test_validate_response_includes_user_id_username_type_staff()
```

Implement: `TokenValidationView` at `/v1/auth/validate/`.

**Step 3: Deploy + E2E**

```bash
# E2E verification
curl /v1/auth/validate/ -H "Authorization: Token <admin-token>"
# → { "user_id": 1, "username": "admin", "user_type": "human", "is_staff": true, "projects": [] }

curl /v1/auth/validate/ -H "Authorization: Token <agent-token>"
# → { "user_id": 2, "username": "executor-1", "user_type": "agent", "is_staff": false, "projects": [] }

curl /v1/auth/validate/ -H "Authorization: Token invalid"
# → 401

curl /v1/auth/validate/
# → 401
```

### Definition of Done

1. Valid human token → returns user_type: "human"
2. Valid agent token → returns user_type: "agent"
3. Invalid/missing token → 401
4. UserProfile auto-created with correct type
5. All existing tests pass

---

## Phase 2: External Identity + Session Records

**Prerequisite for: Slack/mobile/WhatsApp channel adapters, session history.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/models.py` | Add ExternalIdentity, SessionRecord models |
| `prefs/views.py` | Add ExternalIdentityViewSet, SessionHistoryView, ExternalLinkView |
| `prefs/urls.py` | Add routes |
| `vtaskforge/urls.py` | Mount at `/v1/auth/external-link/`, `/v1/external-identities/`, `/v1/profile/sessions/` |
| Migration | Add 2 models |

### TDD Steps

**Step 1: ExternalIdentity model (RED → GREEN)**

```python
# tests/prefs/test_external_identity.py

def test_create_external_identity()
def test_unique_constraint_provider_external_id()
def test_lookup_by_provider_and_external_id()
def test_user_can_have_multiple_identities()
def test_delete_user_cascades_identities()
```

**Step 2: SessionRecord model (RED → GREEN)**

```python
# tests/prefs/test_session_record.py

def test_create_session_record()
def test_ordering_most_recent_first()
def test_filter_by_user()
def test_filter_by_project()
def test_optional_cxdb_context_id()
```

**Step 3: API endpoints (RED → GREEN)**

```python
# tests/prefs/test_external_identity_api.py

def test_list_identities_for_current_user()
def test_create_identity_via_linking_flow()
def test_delete_identity()
def test_lookup_identity_by_provider_external_id()
def test_agents_cannot_manage_identities()

# tests/prefs/test_session_history_api.py

def test_list_sessions_for_current_user()
def test_sessions_ordered_most_recent_first()
def test_filter_sessions_by_project()
def test_agents_cannot_list_sessions()
```

**Step 4: Deploy + E2E**

```bash
# Link a Slack identity
POST /v1/external-identities/ { "provider": "slack", "external_id": "U12345" }
# → 201

# Look it up
GET /v1/external-identities/?provider=slack&external_id=U12345
# → returns linked user

# Create session records
POST /v1/profile/sessions/ { "project_id": "abc", "role": "architect", "channel": "web" }

# List sessions
GET /v1/profile/sessions/
# → ordered list with cxdb links
```

### Definition of Done

1. External identity links a Slack user ID to a vtf user
2. Lookup by provider + external_id returns the vtf user
3. Session records created and listed per user
4. Session records filterable by project
5. Agents rejected from identity/session endpoints
6. All existing tests pass

---

## Phase 3: Agent Locks + Channel Mapping

**Prerequisite for: persistent architect sessions, Slack channel auto-resolution.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/models.py` | Add AgentLock, ChannelProjectMapping models |
| `prefs/views.py` | Add LockViewSet, ChannelMappingViewSet |
| `prefs/urls.py` | Add routes |
| `vtaskforge/urls.py` | Mount at `/v1/locks/`, `/v1/channel-mappings/` |
| Migration | Add 2 models |

### TDD Steps

**Step 1: AgentLock model (RED → GREEN)**

```python
# tests/prefs/test_agent_lock.py

def test_acquire_lock()
def test_unique_constraint_project_role()
def test_second_user_cannot_acquire_same_lock()
def test_same_user_reacquire_returns_existing()
def test_release_lock()
def test_last_activity_updated_on_interaction()
```

**Step 2: ChannelProjectMapping model (RED → GREEN)**

```python
# tests/prefs/test_channel_mapping.py

def test_create_mapping()
def test_unique_constraint_provider_channel()
def test_lookup_project_by_channel()
def test_update_mapping()
def test_delete_mapping()
```

**Step 3: API endpoints (RED → GREEN)**

```python
# tests/prefs/test_lock_api.py

def test_acquire_lock_returns_200()
def test_acquire_locked_by_other_returns_409()
def test_acquire_own_lock_returns_existing()
def test_release_lock()
def test_list_locks_for_project()
def test_lock_response_includes_holder_info()

# tests/prefs/test_channel_mapping_api.py

def test_create_mapping()
def test_list_mappings()
def test_lookup_by_channel()
def test_delete_mapping()
```

**Step 4: Deploy + E2E**

```bash
# Acquire lock
POST /v1/locks/ { "project_id": "abc", "role": "architect" }
# → 200 { lock_id, user, created_at }

# Second user tries
POST /v1/locks/ { "project_id": "abc", "role": "architect" }
# → 409 { "locked_by": "admin", "since": "..." }

# Release
DELETE /v1/locks/{lock_id}/
# → 200

# Channel mapping
POST /v1/channel-mappings/ { "provider": "slack", "channel_id": "C123", "channel_name": "#vtf-dev", "project_id": "abc" }
GET /v1/channel-mappings/?provider=slack&channel_id=C123
# → returns project_id
```

### Definition of Done

1. Lock acquired by one user, rejected for others (409)
2. Same user re-acquiring gets existing lock
3. Lock released successfully
4. Lock list shows holder and last activity
5. Channel mapping created and queried by channel_id
6. All existing tests pass

---

## Phase 4: ProjectMembership (advisory)

### TDD Steps

```python
# tests/prefs/test_project_membership.py

def test_create_membership()
def test_unique_constraint_user_project()
def test_auto_create_owner_on_project_create()  # signal or override
def test_list_memberships_for_user()
def test_validate_endpoint_includes_projects()
def test_membership_roles()
```

### Definition of Done

1. Memberships can be created/listed
2. Owner auto-created when project is created
3. `/v1/auth/validate/` response includes `projects` list
4. No enforcement — all authenticated users still access all projects
5. All existing tests pass

---

## Phase 5: Service Accounts

### TDD Steps

```python
# tests/prefs/test_service_accounts.py

def test_create_service_account_command()
def test_service_account_has_user_type_service()
def test_validate_returns_service_type()
def test_service_account_has_no_usable_password()
```

### Definition of Done

1. Management command creates service account with token
2. Validates as user_type=service
3. All existing tests pass

---

## Phase 6: Access Enforcement

### TDD Steps

```python
# tests/prefs/test_access_enforcement.py

def test_non_member_gets_403_on_project_endpoint()
def test_member_gets_200()
def test_owner_gets_200()
def test_viewer_gets_200_on_read_403_on_write()
def test_agent_auto_membership_on_registration()
def test_staff_bypasses_membership_check()
```

### Definition of Done

1. Non-members get 403 on project-scoped endpoints
2. Members get 200
3. Agents auto-get membership when registered for a project
4. Staff users bypass membership checks
5. All existing tests pass

---

## Dependency Graph

```
Phase 1 (token validation + user_type)
  │
  ├──→ vtf-kb can authenticate requests
  │
  ▼
Phase 2 (external identity + session records)
  │
  ├──→ Channel adapters can resolve users
  │
  ▼
Phase 3 (agent locks + channel mapping)
  │
  ├──→ Persistent architect sessions work
  ├──→ Slack channel → project auto-resolution
  │
  ▼
Phase 4 (project membership — advisory)
  │
  ├──→ /v1/auth/validate/ returns project list
  │
  ▼
Phase 5 (service accounts)
  │
  ├──→ Summarizer authenticates to vtf-kb
  │
  ▼
Phase 6 (access enforcement)
  │
  └──→ Multi-team project isolation
```

Each phase is independently valuable. Phase 1 is the blocker for vtf-kb and the bridge.
