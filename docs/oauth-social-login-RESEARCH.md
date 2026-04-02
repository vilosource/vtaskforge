# OAuth / Social Login — Research

Research into adding "Sign in with GitHub / Google / GitLab / Microsoft" to vtaskforge. This document captures the industry patterns, library options, security considerations, and vtf-specific constraints so a design doc can be written later.

## Problem

vtf currently supports username/password login (session cookies) and token auth (agents/CLI). Adding OAuth social login would:

- Remove password management burden for human users
- Enable SSO with existing identity providers (GitHub, Google, GitLab, Azure AD)
- Align with how modern dev tools handle authentication
- Lay groundwork for enterprise SSO (SAML/OIDC) later

## Current vtf Auth Stack

| Method | Mechanism | Used by |
|--------|-----------|---------|
| Session cookie | Django session + CSRF | Browser (React SPA) |
| Token header | `Authorization: Token <40-char>` (DRF TokenAuth) | Agents, CLI, MCP servers |
| Auth code exchange | Single-use 64-char hex, 60s TTL | vafi-console bridge |

Settings: `DEFAULT_AUTHENTICATION_CLASSES` = TokenAuthentication + SessionAuthentication. Default User model (`django.contrib.auth.models.User`). No custom user model.

Relevant code:
- Login/logout: `src/vtaskforge/urls.py` (api_login, api_logout functions)
- Console code flow: `src/core/views.py` (ConsoleCodeGenerateView, ConsoleCodeExchangeView)
- Frontend login: `web/src/pages/Login.tsx` (username/password form, CSRF handling)
- Auth context: `web/src/App.tsx` (AuthProvider checks token or session)
- API client: `web/src/api/client.ts` (token from localStorage, falls back to session cookie)
- User management: `src/prefs/` (UserProfile with user_type, ExternalIdentity, token validation at `/v1/auth/validate/`)

No OAuth or social auth packages currently installed.

## Industry Standard: Invite-Based OAuth Onboarding

Research of Linear, Vercel, Notion, Slack, GitLab, and GitHub Organizations shows a consistent pattern for admin-controlled environments where not everyone can freely sign up.

### The Universal Flow

```
1. Admin invites by email
   → Creates an INVITATION record (not a user account)
   → Sends invite email with single-use, time-limited link

2. Invitee clicks link
   → App shows OAuth provider buttons ("Sign in with GitHub / Google")
   → Invite token stored in server-side session

3. Invitee authenticates via OAuth provider
   → Provider returns verified email + profile info

4. App checks: does OAuth-verified email match invited email?
   ├─ MATCH    → create user account, link OAuth identity, assign role
   └─ MISMATCH → reject: "Please sign in with the email you were invited with"

5. Invitation consumed (marked used), user is logged in
```

### Key Principle: Invitation vs Authentication Are Separate Concerns

- **Invitation** = authorization grant (permission to join the system)
- **OAuth** = authentication mechanism (proof of identity)
- They are intentionally separate, joined only when the invited email matches the OAuth-verified email
- The user account is created AFTER OAuth, not before — no dangling accounts to hijack

### How Services Handle Specific Scenarios

**Account creation timing:**
All major services (Linear, Vercel, Notion, GitHub) create the user account only after successful OAuth. The invitation is a placeholder/promise, not a user record. This prevents orphaned accounts and invite link hijacking.

**Preventing wrong-person usage:**
- OAuth provider verifies the email (Google/GitHub assert the email is verified)
- Exact email match between invitation and OAuth profile
- Single-use, time-expiring tokens (7-14 days typical)
- Some services bind the invite token to the OAuth `state` parameter to prevent CSRF/fixation

**Email mismatch:**
- Linear, Vercel: hard block — must use the invited email
- Slack: allows if workspace has approved the email's domain
- GitHub Orgs: matches by GitHub username (identity is username-based, not email)

**Open signup vs invite-only:**
Most services support both modes as an admin setting:
- **Open signup**: anyone completing OAuth gets an account
- **Invite-only**: OAuth alone is insufficient — must possess a valid invitation
- **Domain allowlist**: anyone with an email from an approved domain (e.g. `@company.com`) can join without an explicit invite

## Library Options for Django + DRF + React SPA

### Comparison

| Criteria | dj-rest-auth + allauth | django-allauth (solo) | social-auth-app-django | DIY (requests-oauthlib) |
|----------|----------------------|---------------------|----------------------|----------------------|
| DRF TokenAuth | Native. Returns DRF Token on OAuth complete | No DRF integration. Needs custom views | Manual token creation | Fully manual |
| React SPA flow | Designed for it. REST endpoints for callback | Template-based. Needs wrapping | Partial. Callback needs custom SPA work | Full control, full effort |
| Setup effort | ~30 min config | Medium + custom DRF bridge | Medium-high (pipeline config) | 2-4 days |
| Auto User + Token | Out of the box | Creates user, no token | User via pipeline, token is custom | All manual |
| Provider count | 80+ via allauth | 80+ | 50+ | Each hand-coded |
| Community | Active, well-documented | Very active, mature | Maintained, less active | N/A |
| Custom user model | Not required | Not required | Not required | N/A |

### Recommendation: dj-rest-auth + django-allauth

This is the standard combo for DRF + SPA + OAuth. It provides:

- REST endpoints per provider: `POST /auth/github/` accepts OAuth code, returns DRF Token
- Adapter system for customizing user creation (email matching, invite validation)
- Works with existing `TokenAuthentication` — no switch to JWT needed
- Works with default `auth.User` — no custom user model migration

Packages: `dj-rest-auth[with_social]`, `django-allauth`

### How dj-rest-auth Works With a React SPA

```
React                          vtf Backend                    GitHub/Google
  │                                │                              │
  │  User clicks "Sign in          │                              │
  │  with GitHub"                  │                              │
  │──────────────────────────────────────────────────────────────>│
  │                                │           OAuth consent      │
  │<─────────────────────────────────────────── redirect with code│
  │                                │                              │
  │  POST /v1/auth/github/         │                              │
  │  { "code": "abc123" }         │                              │
  │──────────────────────>│        │                              │
  │                       │ Exchange code for                     │
  │                       │ user profile ───────────────────────>│
  │                       │<──────── email, name, avatar ────────│
  │                       │                                       │
  │                       │ Look up/create user                   │
  │                       │ Create DRF Token                      │
  │                       │                                       │
  │<──────────────────────│                                       │
  │  { "key": "token..." }│                                       │
  │                                │                              │
  │  Store token, user is in       │                              │
```

## Providers Worth Supporting

### Tier 1 (implement first)

| Provider | Why |
|----------|-----|
| GitHub | Developer identity. Most vtf users have one. |
| Google | Covers Gmail and Google Workspace. Ubiquitous. |

### Tier 2 (add when needed)

| Provider | Why |
|----------|-----|
| GitLab | vtf's CI/CD runs on GitLab. Relevant for Viloforge team. |
| Microsoft / Azure AD | Viloforge infra is on Azure. Enables enterprise SSO. |

### Tier 3 (config-only, add on demand)

Slack, Apple, Bitbucket, Okta, Auth0, OneLogin, generic OIDC, SAML — all available via allauth, each is just an `INSTALLED_APPS` entry + credentials.

## Security Considerations

### Invite Link Security
- Single-use tokens, invalidated after acceptance
- Time-limited (7-14 day expiry)
- Bind invite token to OAuth `state` parameter to prevent CSRF/token fixation
- Rate-limit invitation creation
- Log all invitation acceptance events for audit

### Email Trust
- Only trust emails marked as "verified" by the OAuth provider
- GitHub users can have multiple emails — must check the `verified` flag
- Google always returns a verified email

### Account Linking Risks
- If a user has both password + OAuth, both should work
- If a user links the wrong OAuth account, admin should be able to unlink
- OAuth provider account compromise = vtf account compromise (standard OAuth risk)

### Session/Token Handling
- OAuth login returns a DRF Token (same as current agent tokens)
- Frontend stores in localStorage (same as current flow)
- Token revocation on logout should also revoke/invalidate OAuth session? (design decision)

## vtf-Specific Considerations

### Integration With Existing Models

vtf already has `ExternalIdentity` (Phase 2 of user management) which maps external provider identities to vtf users. django-allauth has its own `SocialAccount` model that does the same thing. Design decision needed:

| Option | Approach |
|--------|----------|
| A | Use allauth's `SocialAccount` for OAuth, keep `ExternalIdentity` for non-OAuth channel mappings (Slack bot, WhatsApp) |
| B | Bridge allauth's `SocialAccount` to our `ExternalIdentity` via adapter so there's a single source of truth |
| C | Don't use `ExternalIdentity` for OAuth at all, let allauth own that entirely |

Option A is probably cleanest — different concerns, different models.

### New Model Needed: Invitation

```python
class Invitation(models.Model):
    email = models.EmailField()
    role = models.CharField(max_length=20, default="member")  # owner, member, viewer
    token = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    project_id = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(User, null=True, ...)  # who accepted

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["email", "project_id"], ...)
        ]
```

### Configuration Settings

```python
# Toggle: can anyone sign up via OAuth, or invitation-only?
VTF_OAUTH_AUTO_CREATE_USERS = False  # default: invite-only

# Optional: email domains that can self-register without invitation
VTF_OAUTH_ALLOWED_DOMAINS = []  # e.g. ["viloforge.com"]

# Invitation expiry
VTF_INVITATION_EXPIRY_DAYS = 14

# Which providers are enabled
# (controlled via SOCIALACCOUNT_PROVIDERS in Django settings)
```

### Login Page UX

```
┌─────────────────────────────────┐
│  VTaskForge                     │
│                                 │
│  [  Sign in with GitHub   ]    │
│  [  Sign in with Google   ]    │
│                                 │
│  ── or ──                       │
│                                 │
│  [email/username]               │
│  [password     ]                │
│  [        Login        ]        │
│                                 │
│  Invited? Check your email.     │
└─────────────────────────────────┘
```

### Invite Acceptance Page (from invite link)

```
┌─────────────────────────────────┐
│  VTaskForge                     │
│                                 │
│  You've been invited to join    │
│  project "vtf" as a member.    │
│                                 │
│  Sign in to accept:             │
│                                 │
│  [  Sign in with GitHub   ]    │
│  [  Sign in with Google   ]    │
│                                 │
│  ── or set a password ──        │
│                                 │
│  [password     ]                │
│  [confirm      ]                │
│  [    Create Account    ]       │
└─────────────────────────────────┘
```

### Impact on Existing Auth Flows

| Current flow | Impact |
|-------------|--------|
| Username/password login | No change. Still works. |
| Agent token auth | No change. Agents don't use OAuth. |
| Console auth code exchange | No change. Operates post-authentication. |
| `/v1/auth/validate/` | No change. Returns user_type regardless of how user authenticated. |
| `ExternalIdentity` | Separate from OAuth. Used for Slack/WhatsApp channel identity, not login. |

### API Endpoints (estimated)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/auth/github/` | POST | Exchange GitHub OAuth code for DRF Token |
| `/v1/auth/google/` | POST | Exchange Google OAuth code for DRF Token |
| `/v1/auth/gitlab/` | POST | Exchange GitLab OAuth code for DRF Token |
| `/v1/invitations/` | GET/POST | List/create invitations (admin) |
| `/v1/invitations/{token}/` | GET | Validate invite token (public) |
| `/v1/invitations/{token}/accept/` | POST | Accept invitation via OAuth or password |

## Open Questions for Design Phase

1. **allauth SocialAccount vs ExternalIdentity** — use both separately, or bridge them?
2. **Should OAuth users also get a session cookie**, or token-only? (Current SPA uses session for password login, token for agents)
3. **GitHub multi-email** — what if a user's GitHub primary email differs from invited email but a secondary matches?
4. **Admin UI for invitations** — Django admin only, or add to vtf web UI?
5. **Email sending** — vtf doesn't currently send emails. Need SMTP config or use a service (SendGrid, SES)?
6. **Rate limiting** — on OAuth endpoints to prevent brute-force code exchange?
7. **Account merging** — what if someone creates a password account, then later tries OAuth with same email? Auto-merge or manual?

## References

- [django-allauth docs](https://docs.allauth.org/)
- [dj-rest-auth docs](https://dj-rest-auth.readthedocs.io/)
- [GitHub OAuth Apps docs](https://docs.github.com/en/apps/oauth-apps)
- [Google OAuth 2.0 docs](https://developers.google.com/identity/protocols/oauth2)
- vtf user management design: `docs/design/user-management-DESIGN.md`
- vtf user management implementation: `docs/user-management-IMPLEMENTATION-PLAN.md`
