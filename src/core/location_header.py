"""Location header middleware for v2 201 Created responses.

Adds a Location header pointing to the created resource's detail URL
on all v2 201 responses that include an 'id' field.
"""
from django.utils.deprecation import MiddlewareMixin


class LocationHeaderMiddleware(MiddlewareMixin):
    """Add Location header on v2 201 Created responses."""

    def process_response(self, request, response):
        if response.status_code != 201:
            return response
        if not request.path.startswith("/v2/"):
            return response

        # Extract the resource ID from the response body
        try:
            import json
            data = json.loads(response.content)
            resource_id = data.get("id")
            if resource_id:
                # Build location from request path
                # POST /v2/tasks/ → Location: /v2/tasks/{id}/
                base_path = request.path.rstrip("/")
                response["Location"] = f"{base_path}/{resource_id}/"
        except (json.JSONDecodeError, AttributeError):
            pass

        return response
