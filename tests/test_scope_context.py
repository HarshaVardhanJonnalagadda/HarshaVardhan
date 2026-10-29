import unittest

from scope_context import describe_scopes


class ScopeContextTests(unittest.TestCase):
    def test_assignment_and_handler_outside_fragment_are_located(self):
        source = (
            "def review():\n"
            "    key = 'placeholder'\n"
            "    try:\n"
            "        result = operation()\n"
            "    except Exception as exc:\n"
            "        print(key, exc)\n"
        )
        result = describe_scopes(source, 4, 6)

        self.assertIn("Assignment target key: line 2.", result)
        self.assertIn("Exception handler Exception: lines 5-6.", result)
        self.assertIn("do not prove", result)

    def test_nested_assignment_is_not_attributed_to_outer_scope(self):
        source = (
            "def outer():\n"
            "    def inner():\n"
            "        secret = 1\n"
            "    return 0\n"
        )
        result = describe_scopes(source, 4, 4)

        self.assertIn("FUNCTION outer", result)
        self.assertNotIn("Assignment target secret", result)

    def test_complete_function_needs_no_map(self):
        source = "def example():\n    return 1\n"

        self.assertEqual(describe_scopes(source, 1, 2), "")

    def test_map_is_bounded_and_discloses_omission(self):
        source = (
            "def example():\n"
            + "".join(f"    value_{i} = {i}\n" for i in range(100))
        )
        result = describe_scopes(source, 50, 60, max_chars=600)

        self.assertLessEqual(len(result), 600)
        self.assertIn("omitted", result)


if __name__ == "__main__":
    unittest.main()

