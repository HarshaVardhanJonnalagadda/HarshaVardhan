"""Regression tests for bounded caller retrieval."""

import unittest

from verification_context import build_verification_context


SOURCE = """
def read_input():
    return open("request.json").read()

def dispatch():
    return read_input()

def main():
    try:
        return dispatch()
    except OSError:
        return 1
"""


class CallerDepthTests(unittest.TestCase):
    def names(self, depth, include_callers=True):
        result = build_verification_context(
            SOURCE,
            "`read_input` may raise an exception.",
            max_depth=0,
            caller_depth=depth,
            include_callers=include_callers,
        )
        return {block["name"] for block in result["contexts"]}

    def test_caller_depth_boundaries(self):
        for depth, expected in (
            (0, {"read_input"}),
            (1, {"read_input", "dispatch"}),
            (2, {"read_input", "dispatch", "main"}),
        ):
            with self.subTest(depth=depth):
                self.assertEqual(self.names(depth), expected)

    def test_disabled_callers_are_excluded(self):
        self.assertEqual(
            self.names(2, include_callers=False),
            {"read_input"},
        )

    def test_invalid_caller_depth_is_rejected(self):
        for depth in (-1, True, 1.5, "2"):
            with self.subTest(depth=depth):
                with self.assertRaises(ValueError):
                    self.names(depth)

    def test_recursive_callers_terminate(self):
        source = """
def first():
    return second()

def second():
    return first()
"""
        result = build_verification_context(
            source,
            "`first` may recurse.",
            max_depth=0,
            caller_depth=10,
        )
        self.assertEqual(
            {block["name"] for block in result["contexts"]},
            {"first", "second"},
        )


if __name__ == "__main__":
    unittest.main()
