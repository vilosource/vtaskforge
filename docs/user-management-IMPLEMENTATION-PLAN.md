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
- **URL mounting:** prefs URLs currently at `path('v1/profile/', include('prefs.urls'))` in `src/vtaskforge/urls.py`. New auth endpoints mount at `path('v1/auth/...')`

## E2E Verification Protocol

**Every phase MUST be deployed and E2E tested before declaring done.** Unit tests alone are insufficient — they prove the code works in isolation, not that it works in production.

### Deploy to dev

```bash
# 1. Commit all changes
cd ~/GitHub/vtaskforge && git add -A && git commit -m "Phase N: <description>"

# 2. Build with commit hash tag
VTF_SHA=$(git rev-parse --short HEAD)
docker build -f Dockerfile.prod -t harbor.viloforge.com/vafi/vtf:$VTF_SHA .
docker push harbor.viloforge.com/vafi/vtf:$VTF_SHA

# 3. Deploy to vtf-dev
kubectl set image deployment/vtf-api -n vtf-dev vtf-api=harbor.viloforge.com/vafi/vtf:$VTF_SHA
kubectl set image deployment/vtf-mcp -n vtf-dev vtf-mcp=harbor.viloforge.com/vafi/vtf:$VTF_SHA
kubectl rollout status deployment/vtf-api -n vtf-dev --timeout=60s

# 4. Run migration in pod
kubectl exec deployment/vtf-api -n vtf-dev -- python src/manage.py migrate prefs
```

### E2E verification

After deployment, verify each Definition of Done item by calling the live API:

```bash
# Get tokens for testing
# Admin (human) token: query from vtf-dev or use known token
# Agent token: register an agent or use an existing one

# Example: Phase 1 E2E
curl -sk https://vtf.dev.viloforge.com/v1/auth/validate/ \
  -H "Authorization: Token <admin-token>"
# Must return: { "user_id": ..., "user_type": "human", ... }

curl -sk https://vtf.dev.viloforge.com/v1/auth/validate/ \
  -H "Authorization: Token <agent-token>"
# Must return: { "user_type": "agent", ... }

curl -sk https://vtf.dev.viloforge.com/v1/auth/validate/ \
  -H "Authorization: Token invalidgarbage"
# Must return: 401
```

Each phase's "Deploy + E2E" step has the specific curl commands to run. **Do not skip this step.** The phase is not done until the live API responds correctly.

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

Phase is NOT done until ALL of the following are true:

1. Valid human token → `GET /v1/auth/validate/` returns `user_type: "human"`
2. Valid agent token → returns `user_type: "agent"`
3. Invalid/missing token → 401
4. UserProfile auto-created with correct user_type on first access
5. New unit tests pass (minimum 9 tests across test_user_type.py and test_token_validation.py)
6. Full regression suite passes (1200+ existing tests, zero failures)
7. E2E on vtf-dev: curl with admin token, agent token, and invalid token produce correct responses (verified AFTER deployment)
8. Deployed to vtf-dev with commit hash image tag, migration applied

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
# Link a Slack identity (human user only)
curl -sk -X POST https://vtf.dev.viloforge.com/v1/external-identities/ \
  -H "Authorization: Token <admin-token>" -H "Content-Type: application/json" \
  -d '{"provider": "slack", "external_id": "U12345"}'
# → 201

# Look it up
curl -sk https://vtf.dev.viloforge.com/v1/external-identities/?provider=slack\&external_id=U12345 \
  -H "Authorization: Token <admin-token>"
# → returns linked user

# Create a session record (service/controller creates these, not humans)
# Use a service token or simulate from the Django shell:
kubectl exec deployment/vtf-api -n vtf-dev -- python src/manage.py shell -c "
from prefs.models import SessionRecord
from django.contrib.auth.models import User
u = User.objects.get(username='admin')
SessionRecord.objects.create(user=u, project_id='abc', role='architect', channel='web')
print('Created')
"

# List sessions (human API — read only)
curl -sk https://vtf.dev.viloforge.com/v1/profile/sessions/ \
  -H "Authorization: Token <admin-token>"
# → ordered list with cxdb links
```

**Note:** `GET /v1/profile/sessions/` is read-only for humans. Session records are created by the controller, bridge, or service accounts — not by human API calls. The API does NOT expose POST for sessions.

### Definition of Done

Phase is NOT done until ALL of the following are true:

1. External identity links a Slack user ID to a vtf user
2. Lookup by provider + external_id returns the vtf user
3. Session records created and listed per user, ordered most recent first
4. Session records filterable by project
5. Agents rejected from identity and session endpoints (403)
6. New unit tests pass (minimum 14 tests across 4 test files)
7. Full regression suite passes (zero failures)
8. E2E on vtf-dev: create external identity via API, create session records, query both endpoints (verified AFTER deployment)
9. Deployed to vtf-dev with commit hash image tag, migration applied

---

## Phase 3: Agent Locks + Channel Mapping

**Prerequisite for: persistent architect sessions, Slack channel auto-resolution.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/models.py` | Add AgentLock, ChannelProjectMapping models |
| `prefs/serializers.py` | Add serializers for both models |
| `prefs/views.py` | Add LockView (POST to acquire, DELETE to release, GET to list), ChannelMappingViewSet |
| `prefs/urls.py` | Add routes |
| `vtaskforge/urls.py` | Mount at `/v1/locks/`, `/v1/channel-mappings/` |
| Migration | Add 2 models |

### Lock Acquire Logic

The acquire endpoint is NOT a simple create. It has special semantics:

```python
# POST /v1/locks/ { "project_id": "abc", "role": "architect" }
#
# 1. Check if lock exists for (project_id, role)
# 2. If no lock → create it for request.user → 200
# 3. If locked by request.user → return existing lock (reconnect) → 200
# 4. If locked by different user → 409 Conflict with holder info
```

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

Phase is NOT done until ALL of the following are true:

1. Lock acquired by one user, rejected for others with 409 and "locked by {username}"
2. Same user re-acquiring gets existing lock (not error)
3. Lock released successfully, second user can now acquire
4. Lock list shows holder and last activity timestamp
5. Channel mapping created and queried by channel_id → returns project_id
6. New unit tests pass (minimum 12 tests across 4 test files)
7. Full regression suite passes (zero failures)
8. E2E on vtf-dev: acquire lock, verify 409 for second user, release, verify channel mapping (verified AFTER deployment)
9. Deployed to vtf-dev with commit hash image tag, migration applied

---

## Phase 4: ProjectMembership (advisory)

**Prerequisite for: project-scoped access control (Phase 6), validate endpoint project list.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/models.py` | Add ProjectMembership model |
| `prefs/serializers.py` | Add ProjectMembershipSerializer |
| `prefs/views.py` | Add ProjectMembershipViewSet |
| `prefs/urls.py` | Add route |
| `vtaskforge/urls.py` | Mount at `/v1/project-memberships/` |
| `prefs/views.py` (validate) | Update TokenValidationView to include projects list |
| `projects/views.py` or signals | Auto-create owner membership on project creation |
| Migration | Add 1 model |

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

Phase is NOT done until ALL of the following are true:

1. Memberships can be created and listed via API
2. Owner membership auto-created when project is created
3. `GET /v1/auth/validate/` response includes `projects` list with project IDs
4. No enforcement — all authenticated users still access all projects (advisory only)
5. New unit tests pass (minimum 6 tests)
6. Full regression suite passes (zero failures)
7. E2E on vtf-dev: create project → verify owner membership exists, validate token → projects list populated (verified AFTER deployment)
8. Deployed to vtf-dev with commit hash image tag, migration applied

---

## Phase 5: Service Accounts

**Prerequisite for: vtf-kb summarizer auto-writing, auto-discovery job.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/management/commands/create_service_account.py` | New management command |
| `prefs/services.py` | Add `create_service_account(name)` function |
| Migration | None (uses existing UserProfile.user_type="service") |

### TDD Steps

```python
# tests/prefs/test_service_accounts.py

def test_create_service_account_command()
def test_service_account_has_user_type_service()
def test_validate_returns_service_type()
def test_service_account_has_no_usable_password()
```

### Definition of Done

Phase is NOT done until ALL of the following are true:

1. Management command `create_service_account <name>` creates user + token and prints the token
2. `GET /v1/auth/validate/` returns `user_type: "service"` for the service token
3. Service account has no usable password
4. New unit tests pass (minimum 4 tests)
5. Full regression suite passes (zero failures)
6. E2E on vtf-dev: create service account in pod, validate its token via API (verified AFTER deployment)
7. Deployed to vtf-dev with commit hash image tag

---

## Phase 6: Access Enforcement

**Prerequisite for: multi-team project isolation.**

### What Changes

| Component | Change |
|-----------|--------|
| `prefs/permissions.py` | New DRF permission class: `HasProjectMembership` |
| `tasks/views.py` | Add `HasProjectMembership` to permission_classes |
| `workplans/views.py` | Add `HasProjectMembership` to permission_classes |
| `projects/views.py` | Add `HasProjectMembership` to permission_classes |
| `agents/views.py` | Auto-create ProjectMembership on agent registration |
| Migration | None |

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

Phase is NOT done until ALL of the following are true:

1. Non-member user gets 403 on project-scoped endpoints (tasks, workplans for that project)
2. Member user gets 200
3. Owner and viewer roles work correctly (viewer: read OK, write 403)
4. Agents auto-get membership when registered for a project
5. Staff/superuser bypasses membership checks
6. New unit tests pass (minimum 6 tests)
7. Full regression suite passes (zero failures)
8. E2E on vtf-dev: create user without membership → 403 on project endpoint, add membership → 200 (verified AFTER deployment)
9. Deployed to vtf-dev with commit hash image tag

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
