from core.tasks import add


class TestCeleryTasks:
    def test_add_task(self):
        """Call add(2, 3) synchronously via eager mode, verify returns 5."""
        result = add.delay(2, 3)
        assert result.get() == 5
