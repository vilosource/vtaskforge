"""Idempotency-Key middleware for v2 POST mutations.

When a v2 POST request includes an Idempotency-Key header, the response
is cached. Duplicate requests with the same key return the cached response
without re-processing.
"""
import hashlib
import json

from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin


IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
CACHE_PREFIX = "vtf:idempotency:"
CACHE_TTL = 86400  # 24 hours


class IdempotencyMiddleware(MiddlewareMixin):
    """Cache v2 POST responses by Idempotency-Key header."""

    def process_request(self, request):
        if request.method != "POST":
            return None
        if not request.path.startswith("/v2/"):
            return None

        key = request.META.get(IDEMPOTENCY_HEADER)
        if not key:
            return None

        cache_key = f"{CACHE_PREFIX}{hashlib.sha256(key.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached is not None:
            from django.http import JsonResponse
            return JsonResponse(
                cached["data"],
                status=cached["status"],
                content_type="application/json",
            )

        # Store the cache key on the request for process_response
        request._idempotency_cache_key = cache_key
        return None

    def process_response(self, request, response):
        cache_key = getattr(request, "_idempotency_cache_key", None)
        if cache_key is None:
            return response

        # Only cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            try:
                data = json.loads(response.content)
                cache.set(cache_key, {
                    "data": data,
                    "status": response.status_code,
                }, CACHE_TTL)
            except (json.JSONDecodeError, AttributeError):
                pass

        return response
