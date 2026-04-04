"""Step 2: VersionedSerializerMixin tests.

Tests that the mixin selects the correct serializer based on request.version.
"""
import pytest
from unittest.mock import MagicMock
from rest_framework import serializers
from rest_framework.viewsets import ModelViewSet


class V1Serializer(serializers.Serializer):
    pass


class V2Serializer(serializers.Serializer):
    pass


class V2DetailSerializer(serializers.Serializer):
    pass


def _make_viewset_instance(version, action="list", mixin_attrs=None):
    """Create a ViewSet instance with mocked request for testing the mixin."""
    from core.versioning import VersionedSerializerMixin

    attrs = {
        "serializer_class": V1Serializer,
        "serializer_class_v2": V2Serializer,
        "serializer_classes_v2": {},
        "queryset": MagicMock(),
    }
    if mixin_attrs:
        attrs.update(mixin_attrs)

    TestViewSet = type("TestViewSet", (VersionedSerializerMixin, ModelViewSet), attrs)
    instance = TestViewSet.__new__(TestViewSet)
    instance.request = MagicMock()
    instance.request.version = version
    instance.action = action
    instance.kwargs = {}
    instance.format_kwarg = None
    return instance


class TestVersionedSerializerMixin:

    def test_mixin_v1_returns_v1_serializer(self):
        """DoD #1: v1 request returns serializer_class."""
        vs = _make_viewset_instance("v1")
        assert vs.get_serializer_class() is V1Serializer

    def test_mixin_v2_returns_v2_serializer(self):
        """DoD #2: v2 request returns serializer_class_v2."""
        vs = _make_viewset_instance("v2")
        assert vs.get_serializer_class() is V2Serializer

    def test_mixin_v2_action_override(self):
        """DoD #3: v2 with action in serializer_classes_v2 returns that class."""
        vs = _make_viewset_instance(
            "v2", action="retrieve",
            mixin_attrs={"serializer_classes_v2": {"retrieve": V2DetailSerializer}},
        )
        assert vs.get_serializer_class() is V2DetailSerializer

    def test_mixin_v2_fallback_when_not_set(self):
        """DoD #4: v2 with serializer_class_v2=None falls back to v1."""
        vs = _make_viewset_instance("v2", mixin_attrs={"serializer_class_v2": None})
        assert vs.get_serializer_class() is V1Serializer
