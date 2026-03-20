"""Tests for SSE streaming endpoint: GET /v1/events/stream/"""
import json

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APIRequestFactory

from events.stream import event_stream, format_sse, stream_events
from tests.factories import PhaseFactory, TaskEventFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def consume_stream(response):
    """Collect all chunks from a StreamingHttpResponse into a list of strings."""
    chunks = []
    for chunk in response.streaming_content:
        if isinstance(chunk, bytes):
            chunk = chunk.decode()
        chunks.append(chunk)
    return chunks


def parse_sse_chunks(chunks):
    """Parse raw SSE chunk strings into a list of dicts with id/event/data."""
    events = []
    for chunk in chunks:
        lines = chunk.strip().splitlines()
        ev = {}
        for line in lines:
            if line.startswith("id: "):
                ev["id"] = line[4:]
            elif line.startswith("event: "):
                ev["event"] = line[7:]
            elif line.startswith("data: "):
                ev["data"] = json.loads(line[6:])
        if ev:
            events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_user(db):
    user = User.objects.create_user(username="streamuser", password="pass")
    token = Token.objects.create(user=user)
    return user, token


@pytest.fixture
def workplan(db):
    return WorkplanFactory()


@pytest.fixture
def phase(db, workplan):
    return PhaseFactory(workplan=workplan)


@pytest.fixture
def task(db, phase, workplan):
    return TaskFactory(phase=phase, workplan=workplan)


@pytest.fixture
def event(db, task):
    return TaskEventFactory(
        task=task,
        event_type="status_changed",
        data={"from": "draft", "to": "todo"},
    )


def make_authenticated_request(auth_user, path="/v1/events/stream/", **kwargs):
    """Build an authenticated DRF request for the stream_events view."""
    user, token = auth_user
    factory = APIRequestFactory()
    request = factory.get(path, **kwargs)
    # Manually attach auth info that DRF TokenAuthentication uses
    from rest_framework.authtoken.models import Token as DRFToken
    request.META["HTTP_AUTHORIZATION"] = f"Token {token.key}"
    # Force authentication so permission check passes
    from rest_framework.request import Request
    from rest_framework.authentication import TokenAuthentication
    drf_request = Request(request, authenticators=[TokenAuthentication()])
    drf_request.user = user
    drf_request._request = request
    return drf_request


# ---------------------------------------------------------------------------
# Unit tests for format_sse
# ---------------------------------------------------------------------------

class TestFormatSSE:
    def test_sse_format_structure(self):
        result = format_sse("abc123", "status_changed", {"key": "val"})
        assert result.startswith("id: abc123\n")
        assert "event: status_changed\n" in result
        assert 'data: {"key": "val"}\n' in result
        assert result.endswith("\n\n")

    def test_sse_format_data_is_json(self):
        result = format_sse("x", "claimed", {"agent_id": "a1"})
        lines = result.strip().splitlines()
        data_line = next(l for l in lines if l.startswith("data: "))
        payload = json.loads(data_line[6:])
        assert payload == {"agent_id": "a1"}


# ---------------------------------------------------------------------------
# Tests for stream response headers (via DRF APIClient)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreamContentType:
    def _make_client(self, auth_user):
        _, token = auth_user
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return client

    def test_content_type_is_text_event_stream(self, auth_user):
        client = self._make_client(auth_user)
        response = client.get("/v1/events/stream/")
        assert "text/event-stream" in response.get("Content-Type", "")

    def test_cache_control_no_cache(self, auth_user):
        client = self._make_client(auth_user)
        response = client.get("/v1/events/stream/")
        assert response.get("Cache-Control") == "no-cache"

    def test_x_accel_buffering_no(self, auth_user):
        client = self._make_client(auth_user)
        response = client.get("/v1/events/stream/")
        assert response.get("X-Accel-Buffering") == "no"


# ---------------------------------------------------------------------------
# Tests for SSE format (direct generator call with max_iterations=1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreamSSEFormat:
    def _run_stream(self, auth_user, task, query_string=""):
        """Helper: run stream_events view with max_iterations=1 via APIRequestFactory."""
        user, token = auth_user
        factory = APIRequestFactory()
        request = factory.get(f"/v1/events/stream/{query_string}")
        request.META["HTTP_AUTHORIZATION"] = f"Token {token.key}"
        request.user = user
        # Build a DRF-aware request
        from rest_framework.request import Request
        from rest_framework.authentication import TokenAuthentication
        from rest_framework.permissions import IsAuthenticated

        drf_request = Request(request, authenticators=[TokenAuthentication()])
        drf_request.user = user

        from django.http import StreamingHttpResponse
        response = StreamingHttpResponse(
            event_stream(drf_request, max_iterations=1),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    def test_sse_fields_present(self, auth_user, task, event):
        response = self._run_stream(auth_user, task)
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)
        assert len(events) >= 1
        ev = events[0]
        assert "id" in ev
        assert "event" in ev
        assert "data" in ev

    def test_sse_event_id_matches_db_id(self, auth_user, task, event):
        response = self._run_stream(auth_user, task)
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)
        returned_ids = [e["id"] for e in events]
        assert event.id in returned_ids

    def test_sse_event_type_field(self, auth_user, task, event):
        response = self._run_stream(auth_user, task)
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)
        returned = next((e for e in events if e["id"] == event.id), None)
        assert returned is not None
        assert returned["event"] == "status_changed"


# ---------------------------------------------------------------------------
# Tests for filtering (direct generator with max_iterations=1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreamFiltering:
    def _run_stream(self, auth_user, query_string=""):
        user, token = auth_user
        factory = APIRequestFactory()
        request = factory.get(f"/v1/events/stream/{query_string}")
        request.META["HTTP_AUTHORIZATION"] = f"Token {token.key}"
        request.user = user
        from rest_framework.request import Request
        from rest_framework.authentication import TokenAuthentication
        drf_request = Request(request, authenticators=[TokenAuthentication()])
        drf_request.user = user
        from django.http import StreamingHttpResponse
        return StreamingHttpResponse(
            event_stream(drf_request, max_iterations=1),
            content_type="text/event-stream",
        )

    def test_filter_by_type_returns_only_matching(self, auth_user, task):
        e_status = TaskEventFactory(task=task, event_type="status_changed", data={})
        e_claimed = TaskEventFactory(task=task, event_type="claimed", data={"agent_id": "a1"})

        response = self._run_stream(auth_user, "?type=claimed")
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)

        returned_ids = [e["id"] for e in events]
        assert e_claimed.id in returned_ids
        assert e_status.id not in returned_ids

    def test_filter_by_workplan(self, auth_user, phase, workplan, task):
        other_workplan = WorkplanFactory()
        other_phase = PhaseFactory(workplan=other_workplan)
        other_task = TaskFactory(phase=other_phase, workplan=other_workplan)

        e_in = TaskEventFactory(task=task, event_type="status_changed", data={})
        e_out = TaskEventFactory(task=other_task, event_type="status_changed", data={})

        response = self._run_stream(auth_user, f"?workplan={workplan.id}")
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)

        returned_ids = [e["id"] for e in events]
        assert e_in.id in returned_ids
        assert e_out.id not in returned_ids


# ---------------------------------------------------------------------------
# Tests for Last-Event-ID replay
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreamLastEventID:
    def _run_stream(self, auth_user, last_event_id=None):
        user, token = auth_user
        factory = APIRequestFactory()
        request = factory.get("/v1/events/stream/")
        request.META["HTTP_AUTHORIZATION"] = f"Token {token.key}"
        request.user = user
        if last_event_id:
            request.META["HTTP_LAST_EVENT_ID"] = last_event_id

        from rest_framework.request import Request
        from rest_framework.authentication import TokenAuthentication
        drf_request = Request(request, authenticators=[TokenAuthentication()])
        drf_request.user = user

        from django.http import StreamingHttpResponse
        return StreamingHttpResponse(
            event_stream(drf_request, max_iterations=1),
            content_type="text/event-stream",
        )

    def test_last_event_id_excludes_prior_events(self, auth_user, task):
        e1 = TaskEventFactory(task=task, event_type="status_changed", data={"seq": 1})
        e2 = TaskEventFactory(task=task, event_type="claimed", data={"seq": 2})

        response = self._run_stream(auth_user, last_event_id=e1.id)
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)

        returned_ids = [e["id"] for e in events]
        assert e1.id not in returned_ids
        assert e2.id in returned_ids

    def test_no_last_event_id_returns_events_for_this_test(self, auth_user, task):
        e1 = TaskEventFactory(task=task, event_type="status_changed", data={})
        e2 = TaskEventFactory(task=task, event_type="claimed", data={})

        response = self._run_stream(auth_user)
        chunks = consume_stream(response)
        events = parse_sse_chunks(chunks)

        returned_ids = [e["id"] for e in events]
        assert e1.id in returned_ids
        assert e2.id in returned_ids


# ---------------------------------------------------------------------------
# Tests for authentication requirement
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStreamAuthentication:
    def test_auth_required_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/v1/events/stream/")
        assert response.status_code == 401

    def test_session_auth_can_access_stream(self, db):
        """Session (cookie) auth should be accepted by the SSE endpoint."""
        user = User.objects.create_user(username="sseuser", password="ssepass")
        client = APIClient()
        client.login(username="sseuser", password="ssepass")
        response = client.get("/v1/events/stream/")
        assert response.status_code == 200
        assert "text/event-stream" in response.get("Content-Type", "")

    def test_token_auth_still_works_on_stream(self, auth_user):
        """Token auth should remain functional alongside session auth."""
        _, token = auth_user
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/events/stream/")
        assert response.status_code == 200
