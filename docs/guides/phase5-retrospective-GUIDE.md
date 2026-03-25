# Phase 5 Retrospective: HTTP Transport

## Summary

- 7 tasks (P5.1-P5.6 + G5) via simulation, plus 3 fixes from manual smoke test
- Tests: 973 → 991 backend (+18 via simulation), total 1,197
- 0 reworks during simulation, 3 bugs found during manual verification
- Both stdio and streamable HTTP transports verified end-to-end

## What went well

### VtfMCP subclass was an elegant solution (P5.1)
The executor deviated from the spec (per-tool decorators) and instead created a FastMCP subclass that overrides `add_tool()` to auto-wrap sync functions with `sync_to_async`. This is superior: zero tool file changes, all future tools automatically async-safe, enforced at framework level. The judge correctly recognized this as a better design.

### HTTP transport worked quickly (P5.2)
FastMCP's built-in `streamable-http` transport + uvicorn made adding HTTP support a small server.py change. The framework did the heavy lifting.

### Auth integration tested real rejection paths (P5.5)
The auth integration test verified both MCP client behavior on 401 AND raw httpx behavior, making the rejection assertion robust against SDK changes.

## What went wrong

### Three bugs found during manual HTTP smoke test

All three were missed by the simulation's 991 automated tests.

**Bug 1: DNS rebinding protection (421 Misdirected Request)**
FastMCP's default `transport_security.allowed_hosts` only permits `localhost` and `127.0.0.1`. Docker service names (`mcp:8002`) and k8s DNS names are rejected with 421. Fix: disable DNS rebinding protection for HTTP mode (agents are non-browser API clients — the protection is for browser-based attacks).

**Bug 2: Double-import in docker compose (0 tools)**
The docker compose `command: python src/mcp_server/server.py` runs server.py as `__main__`. But tool modules do `from mcp_server.server import mcp`, which re-imports server.py as a regular module — creating a second `mcp` instance. Tools register on the wrong one.

This was already documented in P5.4 tests (which use `python -c` workaround), but the docker compose service still used the broken pattern. Fix: extract `run_server()` function, docker compose calls `python -c "from mcp_server.server import run_server; run_server()"`.

**Bug 3: MCP SDK client API change**
`streamable_http_client()` no longer accepts `headers=` directly. Auth headers must go via `httpx.AsyncClient(headers=...)`. The P5.4/P5.5 tests handled this correctly, but the docs and smoke test used the old API.

### Pattern: simulation tests don't catch deployment bugs

All three bugs are about how the server runs in production (Docker networking, process invocation, SDK client API), not about tool logic. The simulation tested tool functions and even protocol-level stdio — but the HTTP transport running in a Docker container with real networking is a different layer entirely.

This matches the Phase 4 finding: "protocol-level testing is mandatory." Phase 5 adds: **deployment-level testing is also mandatory.** The MCP HTTP server needs a test that starts the docker compose service and connects from another container.

## Key findings

### 1. The __main__ double-import is a Python footgun
When a module is both the entry point (`__main__`) and imported by other modules (`from mcp_server.server import mcp`), Python creates two separate module objects. Anything registered on one is invisible to the other. The fix (extract `run_server()`, import the module normally) is standard Python practice but easy to miss.

### 2. Framework security defaults may block valid use cases
FastMCP's DNS rebinding protection is correct for browser-facing servers but blocks container-to-container communication. The fix (disable for non-browser API clients) is appropriate, but we should document why it's disabled and under what conditions it should be re-enabled.

### 3. Manual smoke tests catch different bugs than automated tests
| Bug | Caught by automated tests? | Caught by smoke test? |
|-----|---------------------------|----------------------|
| DNS rebinding (421) | No | Yes |
| Double-import (0 tools) | Partially (P5.4 documented it) | Yes |
| SDK client API change | No | Yes |
| Django async safety | No (Phase 4) | Yes (Phase 4) |
| Tool logic errors | Yes | N/A |

Automated tests verify behavior. Smoke tests verify deployment. Both are needed.

## Process observations

### Simulation efficiency
7 tasks in simulation, 0 reworks. The spec quality pattern holds: precise specs → first-attempt passes. Phase 5 specs were detailed enough that executors didn't need to guess.

### Sequential was correct for this phase
P5.1 modified server.py (foundation for all other tasks). P5.2 also modified server.py and docker-compose.yml. P5.3 modified server.py. Running these in parallel would have been catastrophic. Only P5.3/P5.4 could have been parallel (separate files), but the small task count didn't justify the overhead.

## Updated baseline

- Backend: 991 tests (from G5, before manual fixes)
- CLI: 206 tests
- Total: 1,197 tests
- MCP tools: 9, across 6 tool files
- Transports: stdio (local), streamable HTTP (remote)
- Auth: TokenAuthMiddleware on HTTP, unauthenticated on stdio
- Docker: `mcp` service on port 8002

## Recommendations

1. Add a deployment-level test that starts docker compose mcp and connects from another container
2. Fix the `python -m` entry point properly (e.g., `__main__.py` that imports and calls `run_server()`)
3. Document the `VTF_MCP_ALLOWED_HOSTS` env var for production deployments
4. Consider adding a health check endpoint (`GET /health`) that doesn't require auth
