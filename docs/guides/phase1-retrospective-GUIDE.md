# Phase 1 Retrospective: MCP Server Skeleton

**Date:** 2026-03-24
**Milestone:** mcp-phase1 (MCP Server Skeleton)
**Workplan:** MCP Server (DcKhKOd37IHFdHNmgUefm)
**Tasks:** 3 (P1.1-P1.3)
**Reworks:** 1 (P1.2 — error response format)
**Test growth:** 857 → 871 backend, 206 CLI unchanged

## Results

| Task | What | Tests Added | Rework | Judge Notes |
|------|------|-------------|--------|-------------|
| P1.1 | MCP SDK dependency | 0 | No | Version pin style inconsistency (open-ended vs ceiling) |
| P1.2 | Server entry point + auth + responses | 8 | Yes | error_response() didn't match spec — nested error object vs flat envelope |
| P1.3 | vtf_board_overview tool | 6 | No | Circular import pattern noted as safe, parameter coercion clean |

## What Worked

### The judge caught a real spec compliance issue
P1.2's executor built error_response() with a nested `{"error": {"code": ..., "message": ..., "details": ...}}` structure — copying the REST API error format. The judge read the SPECIFICATION.md and caught that the MCP response contract requires a flat envelope (`success/data/message/available_actions`) for both success and error cases. This would have propagated to every future tool if uncaught.

### Rework loop worked on first attempt
The executor received the judge feedback, read the spec, fixed error_response() and its tests, and the rework passed on the first re-review. Total overhead: one extra executor + judge cycle (~4 minutes). Without the judge, this bug would have been discovered much later during integration.

### Task specs with SDK details prevented guesswork
After the gap review, we updated the specs with the correct MCP SDK API (FastMCP, @mcp.tool() decorator, server.run(transport="stdio")). The executor didn't need to research the SDK — it just followed the spec. This saved at least one rework cycle.

### Environment change encoded in the task
P1.1 included the Docker rebuild as part of the spec (not a separate controller step). The executor handled it: add dependency → rebuild → restart → verify import → run tests. Zero controller intervention needed.

## What Didn't Work

### Initial specs had gaps
The first version of Phase 1 specs referenced the wrong SDK API (`from mcp.server import Server` instead of `from mcp.server.fastmcp import FastMCP`), didn't specify the exact PyPI package name, and P1.2 only had 3 tests (no auth tests). The gap review before execution caught all of these — but if we'd skipped the review and executed immediately, we would have hit multiple rework cycles.

### The spec was the source of the P1.2 failure
The spec said to match SPECIFICATION.md but also showed an example error_response() with a nested error object. The executor followed the example in the spec rather than reading the SPECIFICATION.md. The spec itself was contradictory — it said "match the spec" but showed a non-spec example.

**Lesson:** Task spec examples must be consistent with referenced design docs. If the spec includes code examples, they must match the actual contract, not a different API's convention.

## Process Observations

### Review gate adds overhead but catches bugs
P1.2 went through: executor (3 min) → judge FAIL (2.5 min) → executor rework (1 min) → judge PASS (2 min) = ~8.5 minutes total. Without the judge, it would have been ~3 minutes but with a latent bug. The 5.5-minute overhead prevented a bug that would have required rework across all Phase 2 tools.

### Spec quality directly affects execution quality
Phase 0 specs were detailed and precise (extracted from a thorough implementation plan). Zero reworks. Phase 1 specs had gaps (wrong SDK API, contradictory examples). One rework. The correlation is clear: invest in spec quality upfront.

### The MCP SDK API research was valuable
Spawning an explore agent to research the actual MCP SDK API before writing specs prevented executor confusion. Without this, every spec would have used the wrong import path and registration pattern.

## Improvements for Phase 2

1. **Verify spec examples against referenced docs** — if a spec includes code examples, cross-check them against the design doc they reference
2. **Include the SPECIFICATION.md response examples in task specs** — don't make the executor discover the format by reading a separate doc; include the relevant section inline
3. **Run CLI tests in every task** — Phase 1 specs included `test_command.cli` which Phase 0 didn't. Maintain this.
4. **Consider end-to-end MCP test** — Phase 1 tests call tool functions directly. Phase 2 should include at least one test that connects via MCP protocol to verify the full stack.

## Metrics

- **Tasks:** 3
- **Executor dispatches:** 4 (3 + 1 rework)
- **Judge dispatches:** 4 (3 + 1 rework review)
- **Reworks:** 1 (P1.2 — error format)
- **Human interventions:** 0
- **Total new tests:** 14
- **Final baseline:** 871 backend, 206 CLI

## Cumulative (Phase 0 + Phase 1)

- **Tasks:** 11 (E0 + P0.1-P0.7 + P1.1-P1.3)
- **Executor dispatches:** 12
- **Judge dispatches:** 12
- **Reworks:** 1
- **Human interventions:** 0
- **Total new tests:** 70
- **Test baseline:** 801 → 871 backend, 206 CLI unchanged
