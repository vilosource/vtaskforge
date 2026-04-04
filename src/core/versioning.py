"""API versioning support for vtaskforge.

VersionedSerializerMixin allows the same ViewSet to serve v1 and v2
serializers based on the URL version prefix (request.version).
"""


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
