# Phase 4c: MCP Server Redesign — SOLID Architecture + v2 Serializers

**Date:** 2026-04-04
**Status:** Approved
**Prerequisite:** Phase 1 (v2 API deployed), Phase 2 (Python SDK)
**Audit:** Full architectural audit performed — see plan file

---

## 1. Problem Statement

The MCP server works but has significant architectural debt:

| Problem | Impact |
|---------|--------|
| 851-line `manage.py` with 13 actions in one function | Violates SRP, untestable, hard to extend |
| Manual dict construction (50+ `json.dumps()` calls) | Drifts from API serializers, duplicated logic |
| Direct ORM imports in tools | Untestable without DB, tight coupling |
| No authorization layer | Any token can access all projects |
| Duplicated field parsing (8+ patterns) | Bugs fixed in one place, not others |
| Inconsistent error handling | Different error formats per tool |

## 2. Design Principles

1. **One tool = one operation** — no action routers
2. **V2 serializers** — single source of truth for entity response shapes
3. **Service layer only** — tools never import ORM models
4. **Decorator-based cross-cutting** — errors, serialization, authorization
5. **Input validation** — centralized parsing, no duplication
6. **Authorization** — project membership checks on all scoped tools

## 3. Architecture

```
@mcp.tool()
@handle_errors          ← catches exceptions → error_response JSON
@serialize_response     ← wraps return dict in envelope + json.dumps
@require_project_access ← checks project membership
def vtf_create_task(title: str, project: str, ...) -> dict:
    task = task_service.create(...)
    return serialize_task(task)    ← uses TaskV2Serializer
```

### 3.1 Decorator Stack

**`@handle_errors`** — outermost. Catches all exceptions and returns standardized error JSON.

**`@serialize_response`** — wraps the tool's return dict in the MCP envelope (`success`, `data`, `message`, `available_actions`) and calls `json.dumps()`. Tools return plain dicts, never call `json.dumps()` themselves.

**`@require_project_access`** — checks that the authenticated user has project membership. Extracts project_id from tool arguments.

### 3.2 Serialization Layer

`mcp_server/serialization.py` provides helpers:
- `serialize_task(task) -> dict` — uses `TaskV2Serializer(task).data`
- `serialize_project(project) -> dict`
- `serialize_workplan(workplan) -> dict`
- `serialize_milestone(milestone) -> dict`

These produce the same entity shapes as the v2 REST API. The MCP envelope wraps them.

### 3.3 Input Parsing

`mcp_server/parsers.py` provides:
- `parse_csv_list(value: str) -> list[str]`
- `parse_bool(value: str) -> bool`
- `parse_json_or_csv(value: str) -> list[str]`
- `parse_test_command(value: str) -> dict`

Used by all tools. No duplication.

## 4. Tool Decomposition

### Current → New

| Current | New Tools |
|---------|-----------|
| `vtf_manage_task(action="create")` | `vtf_create_task` |
| `vtf_manage_task(action="update")` | `vtf_update_task` |
| `vtf_manage_task(action="submit")` | `vtf_submit_task` |
| `vtf_manage_task(action="block")` | `vtf_block_task` |
| `vtf_manage_task(action="unblock")` | `vtf_unblock_task` |
| `vtf_manage_task(action="defer")` | `vtf_defer_task` |
| `vtf_manage_task(action="cancel")` | `vtf_cancel_task` |
| `vtf_manage_task(action="delete")` | `vtf_delete_task` |
| `vtf_manage_task(action="recover")` | `vtf_recover_task` |
| `vtf_manage_task(action="assign")` | `vtf_assign_task` |
| `vtf_manage_task(action="unassign")` | `vtf_unassign_task` |
| `vtf_manage_task(action="note")` | `vtf_add_note` |
| `vtf_manage_workplan(action="create")` | `vtf_create_workplan` |
| `vtf_manage_workplan(action="list")` | `vtf_list_workplans` |
| `vtf_manage_workplan(action="archive")` | `vtf_archive_workplan` |
| `vtf_manage_workplan(action="complete")` | `vtf_complete_workplan` |
| `vtf_manage_milestone(action="create")` | `vtf_create_milestone` |
| `vtf_manage_milestone(action="list")` | `vtf_list_milestones` |
| `vtf_manage_milestone(action="activate")` | `vtf_activate_milestone` |
| `vtf_manage_milestone(action="complete")` | `vtf_complete_milestone` |

### Backward Compatibility

During transition, keep `vtf_manage_task` as a thin router that delegates to the new individual tools with a deprecation warning. Remove after consumers are updated.

## 5. Implementation Steps

| Step | Scope | Files |
|------|-------|-------|
| 1 | Infrastructure: decorators + serialization helpers | `decorators.py`, `serialization.py` |
| 2 | Input parsing: shared validators | `parsers.py` |
| 3 | Decompose task tools | `task_create.py`, `task_update.py`, `task_transitions.py`, `task_assign.py`, `task_notes.py` |
| 4 | Decompose workplan/milestone tools | `workplan_crud.py`, `milestone_crud.py` |
| 5 | Migrate read tools to v2 serializers | `detail.py`, `search.py`, `board.py`, `context.py`, `structure.py` |
| 6 | Authorization layer | `decorators.py` update, all tools |
| 7 | Clean up: remove old files, update tests | Delete old `manage.py`, `workplan.py`, `milestone.py` |

## 6. Verification

Each step: TDD RED → IMPLEMENT → GREEN → REGRESSION → BUILD+DEPLOY → E2E → DoD REVIEW → user sign-off.

E2E: Use MCP tools via `vtf-mcp.dev.viloforge.com` to verify real tool execution.
