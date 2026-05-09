"""
Unit tests for tasks.requires_partition.partition_requires.

This is the pure helper that the 0014 migration uses to split historic
Task.requires JSON values into (deps, tags). Keeping the partition
logic side-effect-free + testable in isolation means the migration's
data-move correctness is verified without an actual migration roundtrip.
"""
import pytest

from tasks.requires_partition import partition_requires


class TestPartitionRequires:
    def test_empty_list(self):
        assert partition_requires([]) == ([], [])

    def test_all_strings_become_tags(self):
        assert partition_requires(["executor", "pi"]) == ([], ["executor", "pi"])

    def test_all_dicts_stay_as_deps(self):
        deps_in = [{"id": "t1", "title": "A"}, {"id": "t2"}]
        deps, tags = partition_requires(deps_in)
        assert deps == deps_in
        assert tags == []

    def test_mixed_partitions_correctly(self):
        mixed = ["executor", {"id": "t1"}, "pi", {"id": "t2"}]
        deps, tags = partition_requires(mixed)
        assert deps == [{"id": "t1"}, {"id": "t2"}]
        assert tags == ["executor", "pi"]

    def test_none_returns_empty_lists(self):
        assert partition_requires(None) == ([], [])

    def test_non_list_returns_empty_lists(self):
        # Defensive fallback — shouldn't occur, but don't crash.
        assert partition_requires("oops") == ([], [])
        assert partition_requires(42) == ([], [])
        assert partition_requires({"id": "t"}) == ([], [])

    def test_unknown_entry_shapes_dropped(self):
        # Lists, ints, None inside the list — neither dep nor tag — silently dropped.
        result = partition_requires(["valid_tag", 42, None, ["nested"], {"id": "t1"}])
        assert result == ([{"id": "t1"}], ["valid_tag"])

    def test_string_order_preserved(self):
        assert partition_requires(["a", "b", "c"])[1] == ["a", "b", "c"]

    def test_dict_order_preserved(self):
        deps_in = [{"id": "t3"}, {"id": "t1"}, {"id": "t2"}]
        assert partition_requires(deps_in)[0] == deps_in

    @pytest.mark.parametrize("value", [
        [],
        ["executor"],
        [{"id": "t1"}],
        ["a", {"id": "t"}, "b"],
    ])
    def test_partition_is_total(self, value):
        """For any list input, deps + (re-stringified tags) == valid partition."""
        deps, tags = partition_requires(value)
        # No overlap: nothing in tags came from deps, and vice versa
        assert all(isinstance(t, str) for t in tags)
        assert all(isinstance(d, dict) for d in deps)
