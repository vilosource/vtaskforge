import json
import time

try:
    from gevent import sleep as _sleep
except ImportError:
    _sleep = time.sleep

from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import TaskEvent


def format_sse(event_id, event_type, data):
    """Format a single SSE message."""
    payload = json.dumps(data)
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


def event_stream(request, max_iterations=None):
    """Generator that polls TaskEvent table and yields SSE-formatted events.

    Args:
        request: Django HTTP request object.
        max_iterations: Number of poll iterations to run. None = infinite.
            Use 1 (or a small integer) in tests for predictable behaviour.
    """
    # --- parse filters ---
    params = request.GET
    workplan = params.get("workplan")
    phase = params.get("phase")
    event_type_filter = params.get("type")

    # --- reconnection support via Last-Event-ID header ---
    # We use timestamp-based cursoring; look up the anchor event's timestamp.
    last_timestamp = None
    last_event_id_header = request.META.get("HTTP_LAST_EVENT_ID") or None
    if last_event_id_header:
        try:
            anchor = TaskEvent.objects.get(pk=last_event_id_header)
            last_timestamp = anchor.timestamp
        except TaskEvent.DoesNotExist:
            pass

    # Track IDs already yielded within a single timestamp bucket to handle
    # ties (two events with identical timestamps).
    seen_ids: set = set()

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        qs = TaskEvent.objects.order_by("timestamp", "id")

        if last_timestamp is not None:
            qs = qs.filter(timestamp__gt=last_timestamp)

        if workplan:
            qs = qs.filter(task__workplan_id=workplan)

        if phase:
            qs = qs.filter(task__phase_id=phase)

        if event_type_filter:
            qs = qs.filter(event_type=event_type_filter)

        for event in qs:
            if event.id in seen_ids:
                continue
            seen_ids.add(event.id)
            last_timestamp = event.timestamp
            yield format_sse(
                event_id=event.id,
                event_type=event.event_type,
                data=event.data,
            )

        iteration += 1

        if max_iterations is None or iteration < max_iterations:
            _sleep(2)


def stream_events(request):
    """SSE streaming endpoint: GET /v1/events/stream/

    Uses a plain Django view (not @api_view) because DRF's content negotiation
    rejects Accept: text/event-stream. Auth is checked manually.
    """
    # Manual auth check — support Token auth, Session auth, and Django login
    user = None

    # Check Django session first (set by login middleware / test client force_login)
    if hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user

    # Fall back to DRF authentication classes
    if user is None:
        for auth_class in [TokenAuthentication(), SessionAuthentication()]:
            try:
                result = auth_class.authenticate(request)
                if result is not None:
                    user = result[0]
                    break
            except (AuthenticationFailed, Exception):
                continue

    if user is None:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)

    response = StreamingHttpResponse(
        event_stream(request),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
