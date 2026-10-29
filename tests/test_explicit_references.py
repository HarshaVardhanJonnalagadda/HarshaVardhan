import unittest

from verification_context import build_verification_context


class ExplicitReferenceTests(unittest.TestCase):
    def test_formatted_function_takes_priority_over_prose_words(self):
        source = (
            "def initialize_demo():\n"
            "    return True\n\n"
            "def timestamp():\n"
            "    return 0\n\n"
            "def order():\n"
            "    return None\n\n"
            "def lines():\n"
            "    return []\n"
        )
        claim = (
            "`initialize_demo` may leave an order incomplete. "
            "Check the timestamp and lines."
        )

        result = build_verification_context(
            source, claim, include_callers=False, max_depth=0
        )

        self.assertEqual(
            result["matched_functions"], ["initialize_demo"]
        )
        names = {block["name"] for block in result["contexts"]}
        self.assertNotIn("timestamp", names)
        self.assertNotIn("order", names)
        self.assertNotIn("lines", names)


if __name__ == "__main__":
    unittest.main()