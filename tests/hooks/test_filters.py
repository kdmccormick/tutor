import typing as t
import unittest

from tutor import hooks


class PluginFiltersTests(unittest.TestCase):
    def tearDown(self) -> None:
        super().tearDown()
        hooks.clear_all(context="tests")

    def run(self, result: t.Any = None) -> t.Any:
        with hooks.enter_context("tests"):
            return super().run(result=result)

    def test_add(self) -> None:
        test_filter = hooks.Filter("tests:count-sheeps")

        @test_filter.add
        def filter1(value: int) -> int:
            return value + 1

        value = hooks.Filter("tests:count-sheeps").apply(0)
        self.assertEqual(1, value)

    def test_add_items(self) -> None:
        test_filter = hooks.Filter("tests:add-sheeps")

        @test_filter.add
        def filter1(sheeps: t.List[int]) -> t.List[int]:
            return sheeps + [0]

        hooks.Filter("tests:add-sheeps").add_item(1)
        hooks.Filter("tests:add-sheeps").add_item(2)
        hooks.Filter("tests:add-sheeps").add_items([3, 4])

        sheeps: t.List[int] = hooks.Filter("tests:add-sheeps").apply([])
        self.assertEqual([0, 1, 2, 3, 4], sheeps)

    def test_filter_context(self) -> None:
        with hooks.enter_context("testcontext"):
            hooks.Filter("test:sheeps").add_item(1)
        hooks.Filter("test:sheeps").add_item(2)

        self.assertEqual([1, 2], hooks.Filter("test:sheeps").apply([]))
        self.assertEqual(
            [1], hooks.Filter("test:sheeps").apply([], context="testcontext")
        )

    def test_clear_context(self) -> None:
        with hooks.enter_context("testcontext"):
            hooks.Filter("test:sheeps").add_item(1)
        hooks.Filter("test:sheeps").add_item(2)

        self.assertEqual([1, 2], hooks.Filter("test:sheeps").apply([]))
        hooks.Filter("test:sheeps").clear(context="testcontext")
        self.assertEqual([2], hooks.Filter("test:sheeps").apply([]))
