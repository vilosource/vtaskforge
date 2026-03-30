# Console Widget Integration — Implementation Plan

> TDD implementation of the console-integration-PLAN.md design.
> Red/green across 3 repos with E2E proof at each phase.
> Created: 2026-03-30

---

## Repo Overview

| Repo | Test framework | E2E approach | Run command |
|------|---------------|-------------|-------------|
| **vtaskforge** (Django) | pytest + Django test client | API-level: register agent with pod_name, verify task serializer | `pytest` |
| **vtaskforge** (React) | Vitest + React Testing Library | Playwright: click buttons, verify widget opens, iframe loads | `npx playwright test` |
| **vafi** (controller) | pytest + httpx mock | Integration: controller reads POD_NAME env, sends in registration/heartbeat | `pytest` |
| **vafi-console** | pytest + k8s mock | E2E (scripts/run-e2e.sh): launch pod with user label, verify isolation | `pytest --e2e` |

---

## Phase Order

```
Phase 1: Pod name plumbing          (vafi + vtf Django)
    │
    └──→ Phase 2: Widget core       (vtf React)
             │
             ├──→ Phase 3: Entry points + Debug  (vtf React, depends on Phase 1 for Debug)
             │
             └──→ Phase 4: Layouts   (vtf React)
                      │
                      └──→ Phase 5: User isolation + final E2E  (vafi-console + Playwright)
```

Phase 2 can start as soon as Phase 1 lands the vtf Django changes (widget needs `claimed_by_pod_name` on tasks). Phase 4 can run in parallel with Phase 3.

---

## Phase 1: Pod Name Plumbing

**Goal**: Agent pods report their pod name to vtf. Task API exposes it for the frontend.

### 1a. vafi repo — Downward API + controller

**RED** — write failing tests first:

```
tests/test_config.py
  - test_config_reads_pod_name_from_env: set POD_NAME env var, verify AgentConfig.pod_name
  - test_config_pod_name_defaults_to_none: no env var, verify AgentConfig.pod_name is None

tests/test_vtf_worksource.py
  - test_register_sends_pod_name: mock VtfClient, verify registration payload includes pod_name
  - test_heartbeat_sends_pod_name: mock VtfClient, verify heartbeat PATCH includes pod_name
  - test_register_without_pod_name: pod_name is None, verify registration still works (field omitted)

tests/test_vtf_client.py
  - test_register_agent_payload: verify POST /v1/agents/ body includes pod_name field
  - test_update_agent_payload: verify PATCH /v1/agents/{id}/ body includes pod_name field
```

**GREEN** — implement:

1. `src/controller/config.py` — add `pod_name: str | None` field, read from `POD_NAME` env var
2. `src/controller/worksources/vtf.py` — include `pod_name` in `register()` and `agent_heartbeat()` payloads
3. `src/controller/vtf_client.py` — pass `pod_name` through in `register_agent()` and `update_agent()`
4. `charts/vafi/templates/executor-deployment.yaml` — add Downward API env var:
   ```yaml
   - name: POD_NAME
     valueFrom:
       fieldRef:
         fieldPath: metadata.name
   ```
5. `charts/vafi/templates/judge-deployment.yaml` — same Downward API env var

**E2E proof** (vafi repo):
```
tests/test_e2e_pod_name.py
  - test_controller_registers_with_pod_name:
      Set POD_NAME=test-executor-abc123 in env
      Start controller with mock vtf server (httpx mock)
      Verify registration POST includes pod_name=test-executor-abc123
      Verify first heartbeat PATCH includes pod_name=test-executor-abc123
```

### 1b. vtaskforge repo — Agent model + task serializer

**RED** — write failing tests first:

```
src/agents/tests/test_agent_pod_name.py
  - test_agent_model_has_pod_name_field: create Agent, set pod_name, save, reload, verify
  - test_agent_serializer_includes_pod_name: serialize agent with pod_name, verify field in output
  - test_agent_registration_accepts_pod_name: POST /v1/agents/ with pod_name, verify stored
  - test_agent_update_pod_name_via_heartbeat: PATCH /v1/agents/{id}/ with pod_name, verify updated
  - test_agent_pod_name_nullable: create agent without pod_name, verify null

src/tasks/tests/test_task_pod_name.py
  - test_task_serializer_includes_claimed_by_pod_name: create task claimed by agent with pod_name, serialize, verify claimed_by_pod_name field
  - test_task_list_includes_claimed_by_pod_name: GET /v1/tasks/, verify field present on claimed tasks
  - test_claimed_by_pod_name_null_when_unclaimed: serialize unclaimed task, verify null
  - test_claimed_by_pod_name_null_when_agent_has_no_pod: claimed by agent with no pod_name, verify null
```

**GREEN** — implement:

1. `src/agents/models.py` — add `pod_name = models.CharField(max_length=255, null=True, blank=True)`
2. `src/agents/migrations/NNNN_add_pod_name.py` — auto-generated migration
3. `src/agents/serializers.py` — add `pod_name` to fields (writable via PATCH)
4. `src/tasks/serializers.py` — add `claimed_by_pod_name` as SerializerMethodField that resolves `claimed_by` → Agent → `pod_name`

**E2E proof** (vtf Django):
```
src/agents/tests/test_agent_pod_name_e2e.py
  - test_full_agent_lifecycle_with_pod_name:
      POST /v1/agents/ {name: "executor-1", tags: ["executor"], pod_name: "vafi-executor-abc123"}
      Verify response includes pod_name
      POST /v1/tasks/{id}/claim/ with agent
      GET /v1/tasks/{id}/
      Verify response includes claimed_by_pod_name = "vafi-executor-abc123"
      PATCH /v1/agents/{id}/ {pod_name: "vafi-executor-xyz789"}  (pod restart)
      GET /v1/tasks/{id}/
      Verify claimed_by_pod_name updated to "vafi-executor-xyz789"
```

### Phase 1 exit gate

- `pytest` passes in both vafi and vtaskforge repos
- Agent registration with pod_name works end-to-end via API
- Task serializer exposes `claimed_by_pod_name`

---

## Phase 2: Widget Core

**Goal**: ConsoleWidgetContext, ConsoleIframe, and WidgetContainer with floating mode. Opening the widget loads the console iframe.

**Repo**: vtaskforge (React)

**RED** — write failing tests first:

```
web/src/components/__tests__/ConsoleWidgetContext.test.tsx
  - test_initial_state_is_closed: useConsoleWidget().isOpen === false
  - test_open_sets_target_and_shows_widget: call open({role: 'architect'}), verify isOpen, target
  - test_close_clears_state: open then close, verify isOpen === false, target === null
  - test_open_with_different_target_replaces: open architect, then open debug, verify target updated
  - test_layout_defaults_to_floating: open widget, verify layout === 'floating'
  - test_state_persists_to_localstorage: open widget, verify localStorage written
  - test_state_restores_from_localstorage: seed localStorage, mount provider, verify restored state

web/src/components/__tests__/ConsoleIframe.test.tsx
  - test_renders_iframe_with_embed_param: verify iframe src includes embed=true
  - test_shows_loading_until_connected: verify loading overlay before postMessage 'connected'
  - test_handles_connected_message: simulate postMessage, verify status updated
  - test_handles_error_message: simulate postMessage error, verify error displayed
  - test_validates_message_origin: message from wrong origin ignored

web/src/components/__tests__/WidgetContainer.test.tsx
  - test_renders_when_open: open context, verify container in DOM
  - test_hidden_when_closed: closed context, verify not in DOM
  - test_floating_position_style: verify position:fixed with correct top/left
  - test_title_bar_shows_role_and_project: open with role=architect project=vtf, verify title
  - test_close_button_calls_close: click X, verify context.close() called
```

**GREEN** — implement:

1. `web/src/contexts/ConsoleWidgetContext.tsx` — context + provider with state management + localStorage persistence
2. `web/src/components/ConsoleIframe.tsx` — iframe with auth code injection, postMessage handler, loading overlay
3. `web/src/components/ConsoleWidget.tsx` — WidgetContainer with floating mode (drag, resize, title bar)
4. `web/src/App.tsx` — mount `ConsoleWidgetProvider` in app layout, render `ConsoleWidget` in `AppLayout`

**E2E proof** (Playwright):
```
web/e2e/console-widget.spec.ts
  - test_open_architect_widget:
      Navigate to home page
      Click "Consult Architect" button
      Verify floating widget container appears
      Verify iframe src contains role=architect and embed=true
      Verify title bar shows "Architect"
      Verify widget has drag handle and close button
```

### Phase 2 exit gate

- Vitest unit tests pass
- Playwright E2E: clicking button opens floating widget with console iframe

---

## Phase 3: Entry Points + Debug

**Goal**: Wire up all 4 entry points. Debug and kanban icon use `claimed_by_pod_name` from Phase 1.

**Repo**: vtaskforge (React)

**RED** — write failing tests first:

```
web/src/pages/__tests__/Home.test.tsx
  - test_consult_architect_button_exists: verify button rendered on home page
  - test_consult_architect_opens_widget: click button, verify context.open({role: 'architect'})

web/src/pages/__tests__/ProjectDashboard.test.tsx
  - test_plan_with_architect_button_exists: verify button rendered
  - test_plan_with_architect_opens_widget_with_project: click, verify context.open({role: 'architect', project: 'proj-id'})

web/src/pages/__tests__/TaskPage.test.tsx
  - test_debug_button_visible_when_doing_with_pod: task doing + claimed + pod_name, verify button
  - test_debug_button_hidden_when_no_pod_name: task doing + claimed, no pod_name, verify hidden
  - test_debug_button_hidden_when_not_doing: task in todo, verify hidden
  - test_debug_opens_widget_with_pod: click debug, verify context.open({pod: 'vafi-executor-abc', command: 'bash'})

web/src/components/__tests__/TaskCard.test.tsx
  - test_terminal_icon_clickable_when_doing_with_pod: task doing + pod_name, click icon, verify widget opens
  - test_terminal_icon_not_clickable_without_pod: task doing, no pod_name, icon is decorative only

web/src/components/__tests__/ConsoleModal.test.tsx
  - test_console_modal_removed: verify ConsoleModal component no longer imported anywhere
```

**GREEN** — implement:

1. `web/src/pages/Home.tsx` — add "Consult Architect" button calling `useConsoleWidget().open({role: 'architect'})`
2. `web/src/pages/ProjectDashboard.tsx` — replace `openConsoleNewTab()` call with `useConsoleWidget().open({role: 'architect', project: project.id})`
3. `web/src/pages/TaskPage.tsx` — replace ConsoleModal with widget: read `task.claimed_by_pod_name`, call `open({pod, command: 'bash'})`
4. `web/src/components/TaskCard.tsx` — wire terminal icon click to `useConsoleWidget().open({pod: task.claimed_by_pod_name, command: 'bash'})`
5. `web/src/api/tasks.ts` — add `claimed_by_pod_name: string | null` to Task interface
6. Delete `web/src/components/ConsoleModal.tsx`

**E2E proof** (Playwright):
```
web/e2e/console-entry-points.spec.ts
  - test_consult_architect_from_home:
      Navigate to /
      Click "Consult Architect"
      Verify widget opens with iframe src containing role=architect

  - test_plan_with_architect_from_project:
      Navigate to /projects/{id}
      Click "Plan with Architect"
      Verify widget opens with iframe src containing role=architect&project={id}

  - test_debug_from_task_page:
      Seed: agent with pod_name, task in doing claimed by agent
      Navigate to /tasks/{id}
      Verify "Debug" button visible
      Click "Debug"
      Verify widget opens with iframe src containing pod={pod_name}&command=bash

  - test_debug_hidden_without_pod_name:
      Seed: agent without pod_name, task in doing claimed by agent
      Navigate to /tasks/{id}
      Verify "Debug" button not visible
```

### Phase 3 exit gate

- All 4 entry points work
- Debug correctly reads `claimed_by_pod_name` from task API
- ConsoleModal removed, no regressions

---

## Phase 4: Layouts

**Goal**: Add docked panel, minimized bar, and pop-out tab. Layout switching preserves terminal session.

**Repo**: vtaskforge (React)

**RED** — write failing tests first:

```
web/src/components/__tests__/WidgetContainer.test.tsx (extend)
  - test_dock_changes_layout: call dock(), verify layout === 'docked'
  - test_docked_applies_fixed_right_style: verify container CSS position:fixed, right:0
  - test_docked_sets_margin_on_main: verify main content has margin-right
  - test_undock_returns_to_floating: dock then float(), verify layout === 'floating'
  - test_minimize_hides_iframe: minimize(), verify iframe container is 1x1px offscreen
  - test_minimize_shows_bar: minimize(), verify minimized bar rendered with role+project
  - test_restore_from_minimized: minimize then restore(), verify previous layout returned
  - test_popout_opens_new_tab: mock window.open, call popOut(), verify URL opened and widget closed
  - test_layout_switch_preserves_iframe_ref: dock/undock, verify same iframe element (not recreated)
  - test_resize_divider_docked: simulate drag on divider, verify panel width changes

web/src/components/__tests__/MinimizedBar.test.tsx
  - test_renders_role_and_project: verify text content
  - test_click_calls_restore: click bar, verify restore() called
```

**GREEN** — implement:

1. `web/src/components/ConsoleWidget.tsx` — add docked mode CSS state, minimize CSS state
2. `web/src/components/MinimizedBar.tsx` — collapsed bar component
3. `web/src/components/ResizeDivider.tsx` — drag handle for docked panel width
4. `web/src/App.tsx` — AppLayout reads `dockWidth` from context, applies `margin-right` when docked

**E2E proof** (Playwright):
```
web/e2e/console-layouts.spec.ts
  - test_floating_to_docked:
      Open widget (floating)
      Click dock icon in title bar
      Verify widget snaps to right edge
      Verify vtf main content has margin-right
      Verify iframe is same (terminal still visible)

  - test_docked_to_floating:
      Open widget, dock it
      Click undock icon
      Verify widget returns to floating position
      Verify vtf main content margin-right removed

  - test_minimize_and_restore:
      Open widget (floating)
      Click minimize icon
      Verify floating container hidden
      Verify minimized bar visible at bottom
      Click minimized bar
      Verify floating container restored

  - test_popout:
      Open widget (floating)
      Click pop-out icon
      Verify new tab opened (intercept window.open)
      Verify in-app widget closed

  - test_drag_floating_widget:
      Open widget
      Drag title bar to new position
      Verify widget moved
      Refresh page
      Verify widget position restored from localStorage
```

### Phase 4 exit gate

- All 3 layouts work and switch without iframe reload
- Drag/resize persists across page refresh
- Pop-out opens correct URL in new tab

---

## Phase 5: User Isolation + Final E2E

**Goal**: Console pods are scoped per user. Full integration E2E across all 3 repos.

### 5a. vafi-console repo — user isolation

**RED** — write failing tests first:

```
tests/test_pod_manager_user.py
  - test_find_or_create_includes_user_label: create pod with username, verify label vafi.viloforge.com/user={username}
  - test_find_or_create_scopes_by_user: create pod for user-a, call find_or_create as user-b, verify new pod created (not reused)
  - test_find_or_create_reuses_same_user_pod: create pod for user-a, call again as user-a, verify same pod returned
  - test_list_pods_filters_by_user: create pods for user-a and user-b, list as user-a, verify only user-a pods

tests/test_api_user.py
  - test_launch_pod_passes_username_to_manager: POST /api/pods with auth, verify PodManager receives username
  - test_pod_labels_include_user: POST /api/pods, verify k8s pod has user label
```

**GREEN** — implement:

1. `src/vafi_console/pods/manager.py` — add `user` parameter to `find_or_create()` and `list_pods()`, add `LABEL_USER = "vafi.viloforge.com/user"` label, include in label selector
2. `src/vafi_console/api/pods.py` — read `request.state.user.username`, pass to PodManager

**E2E proof** (vafi-console):
```
tests/test_e2e_user_isolation.py
  - test_two_users_get_separate_pods:
      Auth as user-a, POST /api/pods {role: architect, project: test}
      Auth as user-b, POST /api/pods {role: architect, project: test}
      Verify two different pod names returned
      GET /api/pods as user-a
      Verify only user-a's pod in list
```

### 5b. Full integration E2E (Playwright against real stack)

```
web/e2e/console-integration.spec.ts

  - test_architect_session_end_to_end:
      Login to vtf web
      Navigate to home page
      Click "Consult Architect"
      Verify floating widget appears
      Wait for iframe to load (postMessage 'connected')
      Verify terminal is interactive (xterm.js rendered)
      Dock the widget
      Navigate to /projects (widget stays open)
      Verify terminal still visible in docked panel
      Minimize widget
      Verify minimized bar at bottom
      Click bar to restore
      Verify docked panel reappears
      Close widget
      Verify confirmation dialog
      Confirm close
      Verify widget gone

  - test_debug_executor_end_to_end:
      Seed: running executor agent with pod_name, task in doing
      Login to vtf web
      Navigate to /tasks/{id}
      Verify "Debug" button visible
      Click "Debug"
      Verify widget opens with bash terminal into executor pod
      Verify terminal shows shell prompt
```

### Phase 5 exit gate

- User isolation: two users get separate pods for same role+project
- Full Playwright E2E: architect session with layout switching
- Full Playwright E2E: debug into running executor

---

## Implementation Order Summary

| Phase | Repo(s) | Deliverables | Tests |
|-------|---------|-------------|-------|
| 1a | vafi | Downward API, controller pod_name | pytest: config, worksource, client |
| 1b | vtaskforge (Django) | Agent model, task serializer | pytest: model, serializer, API lifecycle |
| 2 | vtaskforge (React) | Context, iframe, floating widget | Vitest + Playwright: widget opens |
| 3 | vtaskforge (React) | 4 entry points, remove ConsoleModal | Vitest + Playwright: all buttons work |
| 4 | vtaskforge (React) | Docked, minimized, pop-out, resize | Vitest + Playwright: layout switching |
| 5a | vafi-console | User label, scoped find-or-create | pytest + E2E: user isolation |
| 5b | vtaskforge (Playwright) | Full integration E2E | Playwright: end-to-end flows |

---

## TDD Discipline

Every phase follows strict red/green:

1. **RED**: Write failing tests that describe the expected behavior
2. **GREEN**: Implement the minimum code to make tests pass
3. **REFACTOR**: Clean up without changing behavior
4. **E2E**: Run the phase's E2E test to prove it works from the user's perspective
5. **COMMIT**: One commit per red/green cycle, E2E commit at phase end

No implementation code is written before its test exists. No phase is declared done without its E2E passing.
