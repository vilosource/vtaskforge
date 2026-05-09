"""Tests for ReviewsManager (v2-only cross-project review polling).

See vtaskforge#6 for the silent-fail bug this manager exists to avoid.
"""
import pytest
import respx

from tests.test_entities import V2_TASK


@pytest.fixture
def client():
    from vtf_sdk.client import VtfClient
    router = respx.mock(base_url="http://vtf-test:8000")
    router.start()
    vtf = VtfClient(url="http://vtf-test:8000", token="test-token")
    yield vtf, router
    vtf.close()
    router.stop()


class TestReviewsManager:

    def test_client_has_reviews_manager(self, client):
        vtf, _ = client
        assert hasattr(vtf, "reviews"), "VtfClient must expose `reviews`"

    def test_pending_hits_v2_endpoint(self, client):
        vtf, router = client
        router.get("/v2/reviews/pending/").respond(
            200,
            json={"results": [V2_TASK], "next": None, "previous": None},
        )
        result = vtf.reviews.pending()
        assert len(result.items) == 1
        # Verify it hit the dedicated endpoint, not /v2/tasks/?status=...
        called_url = str(router.calls[0].request.url)
        assert "/v2/reviews/pending/" in called_url
        assert "/v2/tasks/" not in called_url

    def test_pending_returns_task_entities(self, client):
        from vtf_sdk.entities import Task
        vtf, router = client
        router.get("/v2/reviews/pending/").respond(
            200,
            json={"results": [V2_TASK], "next": None, "previous": None},
        )
        result = vtf.reviews.pending()
        assert isinstance(result.items[0], Task)
        assert result.items[0].id == "tsk-abc-123"

    def test_pending_empty(self, client):
        vtf, router = client
        router.get("/v2/reviews/pending/").respond(
            200,
            json={"results": [], "next": None, "previous": None},
        )
        result = vtf.reviews.pending()
        assert result.items == []
        assert result.has_more is False

    def test_pending_passes_page_size(self, client):
        vtf, router = client
        router.get("/v2/reviews/pending/").respond(
            200,
            json={"results": [], "next": None, "previous": None},
        )
        vtf.reviews.pending(page_size=10)
        assert "page_size=10" in str(router.calls[0].request.url)


class TestAsyncReviewsManager:

    @pytest.mark.asyncio
    async def test_async_client_has_reviews_manager(self):
        from vtf_sdk.async_client import AsyncVtfClient
        c = AsyncVtfClient(url="http://vtf-test:8000", token="test-token")
        try:
            assert hasattr(c, "reviews"), "AsyncVtfClient must expose `reviews`"
            assert callable(c.reviews.pending)
        finally:
            await c.close()

    @pytest.mark.asyncio
    async def test_async_pending_hits_v2_endpoint(self):
        from vtf_sdk.async_client import AsyncVtfClient
        with respx.mock(base_url="http://vtf-test:8000") as router:
            router.get("/v2/reviews/pending/").respond(
                200,
                json={"results": [V2_TASK], "next": None, "previous": None},
            )
            c = AsyncVtfClient(url="http://vtf-test:8000", token="test-token")
            try:
                result = await c.reviews.pending()
                assert len(result.items) == 1
                assert result.items[0].id == "tsk-abc-123"
                assert "/v2/reviews/pending/" in str(router.calls[0].request.url)
            finally:
                await c.close()
