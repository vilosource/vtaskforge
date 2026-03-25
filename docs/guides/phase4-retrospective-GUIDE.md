# Phase 4 Retrospective: Polish and Protocol Verification

## Summary

- 5 tasks (P4.1-P4.4 + G4) via simulation, then manual smoke test outside simulation
- Tests: 924 → 973 backend (+49), CLI steady at 206, total 1,179
- Critical bug found during manual verification that 969 tests missed
- MCP server shipped with all 9 tools, auto-discovery, .mcp.json, documentation

## What went well

### Error audit found real issues
P4.1 discovered 9 error paths in manage.py that returned empty `available_actions`. The parametrized test (36 cases) now locks in error quality across all tools.

### Auto-discovery eliminates a conflict class
P4.2 replaced 6 manual import lines in server.py with `pkgutil.iter_modules` + `importlib`. This directly addresses the Phase 3 finding that server.py was the only merge conflict point during parallel execution.

### Performance verified
All read-only tools respond in well under 500ms with 120 seeded tasks. No optimization needed.

## What went wrong

### Critical bug: Django SynchronousOnlyOperation
The manual smoke test (outside simulation) discovered that **every tool fails** when called through the actual MCP stdio protocol. FastMCP runs tools in an async event loop, but all tools use synchronous Django ORM calls. Django's async safety check raises `SynchronousOnlyOperation`.

**Why 969 tests didn't catch this**: every test calls tool functions directly from synchronous Python (via pytest). No test exercised the MCP JSON-RPC transport layer. The protocol handshake (initialize, tools/list) worked fine — only tool execution (tools/call) triggered the error.

**Root cause**: FastMCP's `Tool.run()` calls sync functions directly with `fn(**args)` — no `run_in_executor`, no thread dispatch. When the event loop is running, Django detects the sync ORM call and raises.

**Fix applied**: `os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")` in server.py. Safe for single-client stdio; needs revisiting for multi-client HTTP transport.

### Test pyramid had a gap at the top
The test pyramid claimed to have "E2E" tests, but they were really integration tests calling Python functions. The actual MCP protocol — JSON-RPC framing, subprocess spawning, async execution — was never tested. The 4 new protocol tests (`test_mcp_protocol.py`) fill this gap.

### stdio transport limits deployment options
The `.mcp.json` uses `docker compose exec -T` — this only works when the MCP client runs on the same machine as the Docker stack. For vafi executor containers in Kubernetes, this is a non-starter. Streamable HTTP transport is a prerequisite for production agent deployment.

## Key findings for vafi

### 1. Protocol-level testing is mandatory
Unit tests and integration tests are necessary but not sufficient. Any system that communicates over a protocol (MCP, HTTP, gRPC) needs tests that exercise the actual wire protocol. The simulation's executor→judge loop never tested this because it called functions directly.

### 2. DJANGO_ALLOW_ASYNC_UNSAFE is a temporary fix
For single-client stdio, it's fine. For multi-client HTTP transport (needed for vafi), each request could arrive concurrently. Options:
- Keep `DJANGO_ALLOW_ASYNC_UNSAFE` if the server is still single-threaded (HTTP transport serializes requests)
- Use `sync_to_async(thread_sensitive=True)` wrappers per tool
- Use `anyio.to_thread.run_sync()` in a custom FastMCP tool dispatcher

### 3. Streamable HTTP is the next prerequisite
The MCP spec supports streamable HTTP. The FastMCP SDK supports `mcp.run(transport="streamable-http")`. The server architecture (embedded in Django, calling services directly) works for both transports. Adding HTTP is likely a small change to server.py + a port exposure in Docker.

## Process observations

### Simulation vs reality gap
The simulation protocol exercises tools as Python function calls. The manual smoke test exercised them as MCP protocol calls. The gap between these two is exactly where the bug lived. This validates the Phase 3 retrospective recommendation for real e2e tests.

### Judge skip was correct for Phase 4
All tasks were additive (new test files, new docs, config). Zero reworks. The quality gate + manual smoke test caught the real issue that judges wouldn't have found (they also call functions directly).

## Updated baseline

- Backend: 973 tests (969 from simulation + 4 protocol tests)
- CLI: 206 tests
- Total: 1,179 tests, 0 failures
- MCP tools: 9, across 6 tool files
- Protocol tests: 4 (initialize, success call, error call, full lifecycle)
