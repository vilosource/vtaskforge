"""API versioning support for vtaskforge.

VersionedSerializerMixin allows the same ViewSet to serve v1 and v2
serializers based on the URL version prefix (request.version).

URLPrefixVersioning extracts the version from the URL path prefix
(e.g. /v1/... or /v2/...) without requiring a captured URL kwarg.
"""
import re

from rest_framework.versioning import BaseVersioning


class URLPrefixVersioning(BaseVersioning):
    """Extract API version from URL path prefix.

    Parses /v1/... or /v2/... from the request path. Does not require
    a captured URL kwarg, so existing view methods don't need to accept
    an extra `version` parameter.
    """

    _version_re = re.compile(r"^/(?P<version>v\d+)/")

    def determine_version(self, request, *args, **kwargs):
        match = self._version_re.match(request.path)
        if match:
            return match.group("version")
        return self.default_version


class VersionedSerializerMixin:
    """Mixin for ViewSets that serve both v1 and v2.

    Subclass must define:
        serializer_class = V1Serializer          (existing)
        serializer_class_v2 = V2Serializer        (new)

    Optionally per-action overrides:
        serializer_classes_v2 = {'retrieve': V2DetailSerializer}
    """

    serializer_class_v2 = None
    serializer_classes_v2 = {}

    def get_serializer_class(self):
        if getattr(self.request, "version", "v1") == "v2":
            action_class = self.serializer_classes_v2.get(self.action)
            if action_class:
                return action_class
            if self.serializer_class_v2:
                return self.serializer_class_v2
        return super().get_serializer_class()
