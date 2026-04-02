# Session Record Write API

**Date:** 2026-04-02
**Requestor:** vafi bridge service
**Priority:** Medium
**Blocks:** Bridge session recording (A5 in agent-bridge-service rework plan)

## Problem

The `SessionRecord` model exists (commit `9300560`, user management Phase 2) but only has a read endpoint:

```
GET /v1/profile/sessions/   — list session history (read-only, humans only)
```

The vafi bridge service needs to **create** SessionRecords after each agent interaction to maintain an audit trail. Currently there is no write endpoint, so bridge interactions are unrecorded.

## What's Needed

A `POST /v1/profile/sessions/` endpoint (or separate path like `POST /v1/sessions/`) that accepts:

```json
{
  "project_id": "6udCSkejRVk0vO0k9dxaQ",
  "role": "architect",
  "channel": "web",
  "session_id": "uuid-from-pi-session",
  "cxdb_context_id": 42,
  "started_at": "2026-04-02T10:00:00Z",
  "ended_at": "2026-04-02T10:02:30Z"
}
```

**Auth:** The bridge authenticates with a service account token (`user_type=agent`). The endpoint should accept agent or staff users, not just human users (current `SessionHistoryView` has `IsHumanUser` permission).

**Permissions:** The calling service creates records on behalf of the user who made the request. Either:
- The bridge passes the `user_id` in the request body (bridge acts as proxy)
- Or the endpoint creates the record for the authenticated user (bridge uses the user's token)

Option A (proxy) is simpler for the bridge since it authenticates with a single service token.

## What Exists Today

```python
# src/prefs/models.py
class SessionRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey("tasks.Project", on_delete=models.CASCADE)
    role = models.CharField(max_length=50)
    channel = models.CharField(max_length=50, default="web")
    session_id = models.CharField(max_length=255)
    cxdb_context_id = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

# src/prefs/views.py
class SessionHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsHumanUser]  # read-only, humans only
    def get(self, request): ...
```

## Suggested Implementation

1. Add `post` method to `SessionHistoryView` (or create a separate `SessionCreateView`)
2. Change permission to `IsAuthenticated, IsAgentOrStaff` for POST (keep `IsHumanUser` for GET if desired)
3. Accept `user_id` in request body for proxy mode, or create for `request.user`
4. Return 201 with the created SessionRecord

Estimated effort: small (one view method + permission change).

## Consumer

The vafi bridge service (`src/bridge/app.py`) will call this endpoint after every prompt — both ephemeral and locked sessions — to record the interaction with cxdb trace reference.
