import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def fetch_traces(task_id: str) -> list[dict] | None:
    """Fetch execution traces from CXDB for a given task ID.

    Returns a list of trace dicts, an empty list if no traces found,
    or None if CXDB is unreachable.
    """
    base_url = settings.CXDB_BASE_URL.rstrip("/")
    web_url = settings.CXDB_WEB_URL.rstrip("/")
    timeout = httpx.Timeout(
        connect=settings.CXDB_TIMEOUT_CONNECT,
        read=settings.CXDB_TIMEOUT_READ,
        write=5.0,
        pool=5.0,
    )

    label = f"task:{task_id}"
    url = f"{base_url}/v1/contexts"

    try:
        response = httpx.get(url, params={"labels": label, "limit": 50}, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("CXDB query failed for task %s: %s", task_id, exc)
        return None

    contexts = data.get("contexts")
    if not isinstance(contexts, list):
        logger.warning("CXDB returned unexpected shape for task %s: missing contexts list", task_id)
        return None

    traces = []
    for ctx in contexts:
        # CXDB label filter is prefix-based, so filter client-side for exact match
        ctx_labels = ctx.get("labels") or []
        if label not in ctx_labels:
            continue
        traces.append({
            "context_id": ctx.get("context_id"),
            "title": ctx.get("title", ""),
            "is_live": ctx.get("is_live", False),
            "head_depth": ctx.get("head_depth", 0),
            "created_at_unix_ms": ctx.get("created_at_unix_ms", 0),
            "web_url": f"{web_url}/c/{ctx.get('context_id')}",
        })

    return traces
