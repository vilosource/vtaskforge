# Looking Up Agent Execution Traces in CXDB

## Overview

Every task executed by a vafi agent has its full conversation trace stored in
CXDB. The trace includes every LLM prompt, assistant response, tool call, tool
result, and error that occurred during execution. Traces are tagged with the
vtf task ID for instant lookup.

## URLs

- **Production:** https://cxdb.viloforge.com
- **Dev:** https://cxdb.dev.viloforge.com
- **API base:** `https://cxdb.viloforge.com/v1`

## Finding a trace by task ID

Every CXDB context created by the executor is labeled `task:<vtf-task-id>`.

### API

```bash
# List all contexts (most recent first)
curl https://cxdb.viloforge.com/v1/contexts?limit=10

# Find the context for a specific task — look for the task ID in labels
# Example: task wqudc9fwDTi7yhCfpmafY
curl https://cxdb.viloforge.com/v1/contexts?limit=50 | \
  jq '.contexts[] | select(.labels[] | contains("task:wqudc9fwDTi7yhCfpmafY"))'
```

Response:
```json
{
  "context_id": 3,
  "client_tag": "cxtx/claude",
  "labels": ["cxtx", "claude", "interactive", "task:wqudc9fwDTi7yhCfpmafY"],
  "head_depth": 22,
  "is_live": false,
  "title": "cxtx/claude claude 2026-03-27T20:56:38Z"
}
```

### Web UI

Browse to https://cxdb.viloforge.com — the web UI shows all contexts with
their labels. Click a context to view the full conversation.

## Reading a trace

Once you have the `context_id`, fetch the turns:

```bash
# Get all turns for context 3
curl "https://cxdb.viloforge.com/v1/contexts/3/turns?limit=50&format=typed"
```

Each turn has:
- `item_type`: `system`, `user_input`, `assistant_turn`, or `tool_result`
- `data.turn.text`: The LLM response text
- `data.turn.metrics`: Model name, token counts
- `data.system.title`: System event type (session_start, session_end, etc.)
- `data.user_input.text`: The prompt sent to the LLM

## Trace structure

A typical task trace looks like:

| Turn | Type | Content |
|------|------|---------|
| 1 | system | session_start — child command, args, timestamps |
| 2 | user_input | Task prompt with spec |
| 3 | assistant_turn | LLM reasoning and plan |
| 4 | tool_result | File write / command execution result |
| ... | ... | More tool calls and responses |
| N-1 | assistant_turn | Completion summary |
| N | system | session_end — exit code, success flag |

## Provenance

The first turn includes provenance metadata:

```json
{
  "provenance": {
    "host_name": "executor-pool-xxx",
    "env_vars": {
      "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"
    },
    "sdk_name": "cxtx",
    "process_owner": "agent"
  }
}
```

This tells you which executor pod ran the task and through which API endpoint.

## Rework traces

When a task is reworked (judge rejects, executor retries), each attempt creates
a separate CXDB context, all tagged with the same `task:<id>` label. Multiple
contexts for the same task ID means multiple execution attempts.

## In-cluster access

From within the k8s cluster, cxdb is reachable at:
```
http://cxdb-server.vafi-agents.svc.cluster.local
```
