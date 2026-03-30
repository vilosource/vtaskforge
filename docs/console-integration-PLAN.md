# vafi-console Integration Plan

> Phase 4 of the vafi-console rollout. Adds terminal access to agent pods directly from the vtf web UI.
> Created: 2026-03-30

---

## Context

vafi-console is deployed at `console.dev.viloforge.com` with:
- Backend: FastAPI + k8s exec WebSocket proxy
- Frontend: xterm.js SPA with standalone and embedded modes
- Auth: single-use code exchange via vtf (`/v1/auth/code/` and `/v1/auth/exchange/`)
- URL contract: `?role=architect&project={slug}` (launch mode) or `?pod={name}` (connect mode)
- Embedding: `embed=true` parameter renders terminal-only (no sidebar/chrome)

vtf already has:
- `web/src/api/console.ts` — `buildConsoleUrl()`, `generateAuthCode()`, `buildAuthenticatedConsoleUrl()`, `openConsoleNewTab()`
- Django `ConsoleAuthCode` model + endpoints for code generation and exchange
- Agent model with status/heartbeat but no pod name tracking

---

## Design

### Terminal widget with three layouts

A single iframe loads vafi-console in embedded mode. The user controls how it appears via three layouts. The iframe stays in a single fixed-position container at all times — layout switches change CSS properties (position, size, z-index), never move the DOM node. This avoids browser garbage-collecting the iframe's JavaScript context, which would kill the WebSocket connection.

**1. Floating window (default)**
- `position: fixed` overlay on top of vtf, positioned via CSS `top`/`left`
- Draggable, resizable
- Minimizable to a small bar/icon at the bottom of the screen
- Persists across vtf page navigation (lives outside the route outlet)
- Default size: ~600x400px, minimum: 400x300px

**2. Docked panel**
- Same iframe container repositioned: `position: fixed; right: 0; top: 0; height: 100vh; width: {user-set}`
- vtf main content gets a `margin-right` matching the panel width
- Good for longer sessions (architect planning alongside task board)
- User docks via an icon on the floating window title bar
- Resizable divider controls panel width

**3. Pop-out tab**
- Opens the same console URL in a new browser tab (full standalone mode)
- Closes the in-app widget
- For when the user wants full-screen terminal

### Layout switching

The iframe stays in one DOM container. Layout changes are purely CSS — position, dimensions, and z-index. No DOM reparenting, no reload, no reconnection. The WebSocket connection in the iframe survives all layout transitions because the iframe's JavaScript context is never destroyed.

Widget state (current layout, position, size) persists in localStorage so it survives page refreshes. The terminal session itself requires reconnection after a page refresh (iframe reloads), but the auto-reconnect logic in vafi-console handles this transparently.

### Widget lifecycle

- **Open**: user clicks a console button anywhere in vtf. If a widget is already open, bring it to front / restore from minimized. If the new target differs (different project/pod), confirm before replacing.
- **Minimize**: collapse to a small bar showing role + project name. Click to restore.
- **Close**: user clicks X. Confirm if terminal session is active ("Terminal session is running. Close anyway?"). Closing destroys the iframe.
- **Navigate away**: widget persists across vtf route changes (it's mounted at the app layout level, outside `<Outlet/>`).

---

## Entry points

### 1. "Plan with Architect" — project dashboard

- **Location**: `ProjectDashboard.tsx`, action area near project header
- **Behavior**: opens floating terminal widget with `role=architect&project={slug}`
- **When visible**: always (any project can have an architect session)

### 2. "Consult Architect" — home page

- **Location**: `Home.tsx`, prominent action button/card
- **Behavior**: opens floating terminal widget with `role=architect` (no project — greenfield or general consultation)
- **When visible**: always

### 3. "Debug" — task detail

- **Location**: `TaskPage.tsx`, action area
- **Behavior**: opens floating terminal widget with `pod={agent_pod}&command=bash`
- **When visible**: task is in `doing` status and has a claimed agent with a known pod

### 4. Terminal icon — kanban card

- **Location**: `TaskCard.tsx`, inline icon
- **Behavior**: same as Debug — opens widget connecting to the agent's pod
- **When visible**: task is in `doing` status with claimed agent

---

## Components

### ConsoleWidget

Top-level widget component, mounted once in the app layout (outside route outlet).

```
Props: none (reads state from ConsoleWidgetContext)

State (via context):
  - isOpen: boolean
  - layout: 'floating' | 'docked' | 'minimized'
  - target: { role?, project?, workplan?, pod?, command? }
  - position: { x, y } (floating only)
  - size: { width, height }
```

Renders a single WidgetContainer with CSS-driven layout modes. Mounted in AppLayout (outside `<Outlet/>`), persists across route changes.

### ConsoleWidgetContext

React context + provider at the app layout level. Exposes:

```ts
interface ConsoleWidgetAPI {
  open(params: ConsoleUrlParams): void;   // open or replace session
  close(): void;                          // destroy session
  minimize(): void;                       // collapse to bar
  restore(): void;                        // restore from minimized
  dock(): void;                           // switch to panel layout
  float(): void;                          // switch to floating layout
  popOut(): void;                         // open in new tab, close widget
  isOpen: boolean;
  layout: 'floating' | 'docked' | 'minimized';
  target: ConsoleUrlParams | null;
}
```

### WidgetContainer

Single fixed-position div that wraps the iframe. All layout modes are CSS states on this one container:

- **Floating**: `position: fixed; top/left` set by drag, `width/height` set by resize. Title bar with drag handle. Resize handle at bottom-right corner. Constrained to viewport bounds.
- **Docked**: `position: fixed; right: 0; top: 0; height: 100vh; width: {panel-width}`. A separate resizable divider overlay controls the width. AppLayout's main content gets `margin-right: {panel-width}` via context.
- **Minimized**: `position: fixed; bottom: 0; right: 16px; width: auto; height: auto`. Collapsed to a small bar. Iframe rendered at 1x1px offscreen (not `display: none`) to keep the WebSocket alive. If the connection drops anyway, vafi-console auto-reconnects with exponential backoff.

Title bar shows: role icon + project name (or "Architect"), layout toggle icons (dock/undock, pop-out, minimize, close). Uses pointer events for drag/resize (not HTML5 drag API).

### MinimizedBar

- Fixed-position bar at bottom of screen
- Shows: role icon, project name, "click to restore"
- Subtle pulse/indicator if terminal has new output (optional, stretch)

### ConsoleIframe

- Renders the `<iframe>` element with the authenticated console URL
- Handles postMessage communication:
  - Receives: `ready`, `connected`, `disconnected`, `error`
  - Sends: `resize`, `disconnect`, `focus`
- Shows loading overlay until `connected` message received
- Origin validation on all messages

---

## Data requirements

### Pod name resolution

For Debug and kanban terminal buttons to work, vtf needs to know which pod an agent is running in. The mapping chain is: Task (`claimed_by` = agent NanoID) → Agent → ??? → Pod.

**Decision: Downward API + controller reports pod_name to vtf.**

The controller is a worker process inside the pod — it has no k8s API access and no awareness of k8s infrastructure. But the pod spec can inject `POD_NAME` via the standard k8s Downward API (`metadata.name` as env var). The controller reads it like any other env var and includes it in its registration and heartbeat payloads.

**Changes required across 3 repos:**

1. **vafi repo** (Helm templates + controller):
   - Add `POD_NAME` env var via Downward API `fieldRef` to executor and judge Deployment templates
   - Controller config reads `POD_NAME` from env
   - Controller includes `pod_name` in registration payload (`POST /v1/agents/`) and heartbeat payload (`PATCH /v1/agents/{id}/`)
   - On pod restart (new pod name), re-registration updates the stored value

2. **vtaskforge repo** (Django model + API):
   - Add `pod_name` CharField (nullable, blank) to Agent model + migration
   - Update AgentSerializer to include `pod_name` (read-only from API, writable via PATCH)
   - Frontend reads `pod_name` from agent API when rendering Debug/terminal buttons

3. **vafi-console repo** (PodManager):
   - Console-launched pods also need `POD_NAME` Downward API env var in the pod spec built by PodManager
   - No other changes — the console already accepts `?pod={name}` in its URL contract

**Scaling**: each Deployment replica gets its own pod name, registers as a separate agent, and reports its own `pod_name`. Works for 1 or N replicas. Pod restarts update the value via re-registration.

### Frontend data flow for Debug button

```
TaskPage → task.claimed_by (agent NanoID)
        → fetch agent by ID → agent.pod_name
        → open widget with ?pod={pod_name}&command=bash
```

This requires a lightweight agent lookup. Options:
- Inline the agent's `pod_name` in the task serializer (avoids extra fetch)
- Or fetch agent on demand when Debug button is clicked

Inlining is simpler — add `claimed_by_pod_name` as a read-only field on both the task list and task detail serializers that resolves through `claimed_by` → Agent → `pod_name`. This ensures the kanban board (task list) and task detail page both have the pod name without an extra API call.

---

## Deliverables

| # | Deliverable | Details |
|---|-------------|---------|
| 4.1 | ConsoleWidgetContext + provider | Context, state management, localStorage persistence for layout/position/size. Mount provider in App.tsx alongside existing AuthProvider and ActiveProjectProvider. |
| 4.2 | ConsoleIframe component | Iframe rendering, auth code injection via existing `console.ts` utilities, postMessage protocol (ready/connected/disconnected/error), loading overlay, origin validation locked to console domain. |
| 4.3 | WidgetContainer + floating mode | Single fixed-position container with CSS-driven layout states. Floating: draggable (pointer events), resizable, viewport-constrained. Title bar with layout controls. |
| 4.4 | Docked mode | CSS repositions container to right edge. Resizable divider overlay. AppLayout reads dock width from context and applies `margin-right` to main content area. |
| 4.5 | Minimized mode | Container collapses to small bar at bottom of viewport. Iframe hidden. Click to restore previous layout. |
| 4.6 | Pop-out to new tab | Opens console URL in new browser tab via `openConsoleNewTab()` (already exists in `console.ts`). Closes in-app widget. |
| 4.7 | "Consult Architect" on Home | Button/card on Home.tsx dashboard, opens widget with `role=architect`. |
| 4.8 | "Plan with Architect" on ProjectDashboard | Button in ProjectDashboard.tsx header area, opens widget with `role=architect&project={slug}`. |
| 4.9 | "Debug" on TaskPage | Button in TaskPage.tsx actions, opens widget with `pod={agent_pod}&command=bash`. Visible when task is `doing` with claimed agent. |
| 4.10 | Terminal icon on TaskCard | Wire existing terminal icon in TaskCard.tsx (already renders for doing+claimed tasks) to open widget. |
| 4.11 | Pod name plumbing (3 repos) | **vafi**: Add Downward API `POD_NAME` env var to Helm executor/judge templates + console PodManager pod spec. Controller config reads it, includes in registration + heartbeat payloads. **vtf**: Add `pod_name` to Agent model + migration + serializer. Add `claimed_by_pod_name` annotated field to task serializer. **vafi-console**: no changes (already accepts `?pod={name}`). |
| 4.12 | Remove ConsoleModal | Replace existing `ConsoleModal.tsx` with ConsoleWidget. Migrate any pages using ConsoleModal to use ConsoleWidgetContext.open() instead. |
| 4.13 | User isolation on console pods | vafi-console: thread `username` from auth middleware to PodManager. Add `vafi.viloforge.com/user` label to pods. Include user in find-or-create label selector. Each user gets their own pod per role+project. |
| 4.14 | Tests | Unit tests for context/state logic, component tests for layout modes, integration test for postMessage flow. |

---

## Exit criteria

- Click "Consult Architect" on home page — floating terminal opens, architect session starts (no project)
- Click "Plan with Architect" on a project — floating terminal opens, architect has project context
- Click "Debug" on a running task — floating terminal opens with bash shell into executor pod
- Drag the floating window around, resize it — position persists
- Click dock icon — terminal snaps to right panel, vtf content shrinks, WebSocket stays connected (no reconnect)
- Click undock — returns to floating, WebSocket stays connected
- Minimize — bar appears at bottom, click to restore
- Pop out — new tab opens with full console, in-app widget closes
- Navigate between vtf pages — widget stays open
- Close widget with active session — confirmation prompt appears
- Refresh page — widget state (layout, position) restored from localStorage (session itself requires reconnect)

---

## Resolved gaps

### G1: iframe reparenting breaks WebSocket — RESOLVED

Moving an iframe between DOM containers risks browser garbage-collecting the JavaScript context, killing the WebSocket. **Fix**: keep the iframe in a single fixed-position container at all times. Layout switches are pure CSS changes (position, size, z-index). No DOM reparenting ever happens. Validated by the fact that CSS `display: none` on an iframe preserves its JavaScript context in all modern browsers, and vafi-console has auto-reconnect with exponential backoff as a safety net.

### G2: ConsoleModal already exists — RESOLVED

`web/src/components/ConsoleModal.tsx` already implements a basic iframe + postMessage modal for the console. Deliverable 4.12 replaces it with the new widget. All call sites migrate to `ConsoleWidgetContext.open()`.

### G3: postMessage origin uses wildcard — RESOLVED

vafi-console's `embed.js` sends postMessage with `'*'` origin. Must be locked to allowed origins (`vtf.viloforge.com`, `vtf.dev.viloforge.com`) before production. This is a vafi-console fix, not a vtf fix. Track as a vafi-console hardening item (Phase 5 scope).

### G4: Pod name resolution — RESOLVED

Nobody in the system knew both the agent ID and the pod name. The controller (worker process inside the pod) knows its agent ID but not its pod name. The console PodManager knows pod names but not agent IDs. vtf knows agent IDs but not pod names.

**Fix**: k8s Downward API injects `POD_NAME` env var into the pod spec. The controller reads it and reports it to vtf during registration and heartbeat. vtf stores it on the Agent model. Frontend reads it via the task's `claimed_by` → agent → `pod_name` join. See "Data requirements" section for full details.

### G5: Existing Debug button is broken — RESOLVED

`TaskPage.tsx` line 105 passes `task.claimed_by` (agent NanoID) as the `pod` parameter to ConsoleModal. The console expects a k8s pod name, not a NanoID. This has never worked. **Fix**: deliverable 4.9 replaces this with the correct flow — look up agent's `pod_name`, pass that to the widget.

### G6: Console can only exec into same-namespace pods — NOTED

Console RBAC is a namespace-scoped Role (not ClusterRole). Console PodManager reads its namespace from `VAFI_NAMESPACE` env var (set via Downward API). Currently all dev pods (executor, judge, console) are in `vafi-dev`. This works today but will need ClusterRole or per-namespace console instances if pods spread across namespaces in production. Not a blocker for this phase — track as Phase 5 hardening.

### G7: VITE_CONSOLE_URL not configured for production — NOTED

`console.ts` and `ConsoleModal.tsx` both read `VITE_CONSOLE_URL` env var with fallback to `https://console.dev.viloforge.com`. This is fine for dev but needs to be configurable per environment for production (e.g., `console.viloforge.com`). Not a blocker — the hardcoded default works for dev. Track as Phase 5 hardening when production overlay is created.

### G8: Cross-origin iframe security — VERIFIED OK

Checked all layers for iframe embedding from `vtf.dev.viloforge.com` → `console.dev.viloforge.com`:
- **X-Frame-Options / CSP frame-ancestors**: not set on console (allows embedding from any origin). Should be locked down in Phase 5 to only allow vtf origins.
- **Cookie SameSite**: set to `lax` in console auth middleware — cookies will be sent in cross-origin iframe requests. Correct.
- **Traefik IngressRoute**: no response headers middleware blocking embedding.
- **CORS**: not needed — the iframe loads its own origin, no cross-origin API calls from iframe to vtf.

No blockers. Phase 5 should add explicit `Content-Security-Policy: frame-ancestors` header.

### G9: Minimized widget may trigger pod cleanup — RESOLVED

When the widget is minimized, the iframe is hidden. The browser may throttle or drop the WebSocket. When the WebSocket disconnects, the console decrements `active_connections` to 0 and the cleanup loop deletes the pod after 30 minutes of "idle."

This only affects **console-launched architect pods** (label `managed-by: console`). Debug connects to Helm-deployed executor/judge pods — those are k8s Deployments, never cleaned up by the console.

**Accepted behavior**: if the pod dies, the user reopens the widget and gets a new pod with a fresh Claude session. The architect's work product survives — tasks created via MCP are in vtf, committed code is in the repo, conversation traces are in cxdb. The new session can discover all prior work via vtf MCP tools.

To reduce the chance of this happening: render the minimized iframe at 1x1px offscreen rather than `display: none`, which is more likely to keep the WebSocket alive. But if it does drop, auto-reconnect + pod recreation is the fallback.

### G10: No user isolation on console pod reuse — IN SCOPE

Console find-or-create matches pods by `role + project` labels only. Two users opening "Plan with Architect" for the same project share the same pod. This is a problem when embedding in vtf where multiple users exist.

**Fix (vafi-console repo only)**: the auth middleware already populates `request.state.user.username` on every authenticated request. Thread it through:

1. Add `vafi.viloforge.com/user: {username}` label to pods on creation
2. Pass `username` from API endpoint (`request.state.user.username`) to PodManager `find_or_create()`
3. Include user in the label selector: match on `role + project + user`
4. Each user gets their own pod per role+project combination

This is a contained change in vafi-console — no vtf or vafi changes needed. Added as deliverable 4.13.

---

## Dependencies

- vafi-console Phases 1-3 deployed and working (done)
- vtf auth code endpoints working (done)
- `web/src/api/console.ts` utilities (done)
- Agent `pod_name` field (deliverable 4.11, new)

---

## Out of scope

- Terminal I/O recording/playback
- Multi-terminal (multiple widgets open simultaneously) — v1 is single widget
- Console access controls beyond auth (e.g., role-based pod access restrictions)
