"""DRF ViewSet mixin for automatic access tracking."""

from .services import record_access


class TrackAccessMixin:
    """Records resource access on successful retrieve().

    Add to a ViewSet and set `access_resource_type` to enable tracking.
    Uses the object's `title` or `name` attribute for the display title.
    """

    access_resource_type: str = ""

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == 200 and self.access_resource_type:
            obj = self.get_object()
            title = getattr(obj, "title", getattr(obj, "name", str(obj)))
            status = getattr(obj, "status", "")
            record_access(
                request.user,
                self.access_resource_type,
                str(obj.pk),
                title,
                status,
            )
        return response
