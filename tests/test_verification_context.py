"""Offline tests for source retrieval."""

import unittest

from verification_context import build_verification_context


class RetrievalTests(unittest.TestCase):
    def test_capitalized_name_matches_function(self):
        source = (
            "def release(value):\n"
            "    return value\n"
        )

        result = build_verification_context(
            source,
            "Release may behave incorrectly.",
            include_callers=False,
        )

        self.assertIn("release", result["matched_functions"])

    def test_helper_included_and_unrelated_function_excluded(self):
        source = (
            "def check(value):\n"
            "    return value > 0\n\n"
            "def process(value):\n"
            "    return check(value)\n\n"
            "def unrelated():\n"
            "    return 42\n"
        )

        result = build_verification_context(
            source,
            "Inspect process.",
            include_callers=False,
        )

        names = {block["name"] for block in result["contexts"]}

        self.assertIn("process", names)
        self.assertIn("check", names)
        self.assertNotIn("unrelated", names)


if __name__ == "__main__":
    unittest.main()