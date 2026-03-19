import pytest
from core.mixins import NanoIDMixin, TimestampMixin, generate_nanoid


class TestGenerateNanoid:
    def test_returns_string(self):
        result = generate_nanoid()
        assert isinstance(result, str)

    def test_length_is_21(self):
        result = generate_nanoid()
        assert len(result) == 21

    def test_two_calls_produce_different_values(self):
        id1 = generate_nanoid()
        id2 = generate_nanoid()
        assert id1 != id2


class TestNanoIDMixin:
    def test_id_field_exists(self):
        field = NanoIDMixin._meta.get_field("id")
        assert field.primary_key is True
        assert field.max_length == 21
        assert field.default is generate_nanoid
        assert field.editable is False

    def test_is_abstract(self):
        assert NanoIDMixin._meta.abstract is True


class TestTimestampMixin:
    def test_created_at_field(self):
        field = TimestampMixin._meta.get_field("created_at")
        assert field.auto_now_add is True

    def test_updated_at_field(self):
        field = TimestampMixin._meta.get_field("updated_at")
        assert field.auto_now is True

    def test_is_abstract(self):
        assert TimestampMixin._meta.abstract is True
