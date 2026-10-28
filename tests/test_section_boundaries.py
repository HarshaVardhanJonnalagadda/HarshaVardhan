"""Offline regression tests for source-section boundaries."""

import ast
import unittest

from source_context import make_sections


class SectionBoundaryTests(unittest.TestCase):
    def assert_coverage(self, source, sections, limit):
        covered = {
            number
            for section in sections
            for number in range(
                section["start_line"], section["end_line"] + 1
            )
        }
        self.assertEqual(
            covered, set(range(1, len(source.splitlines()) + 1))
        )
        self.assertTrue(
            all(len(section["context"]) <= limit for section in sections)
        )

    def assert_function_together(self, source, sections, name):
        node = next(
            item for item in ast.walk(ast.parse(source))
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == name
        )
        start = min(
            [node.lineno] + [d.lineno for d in node.decorator_list]
        )
        self.assertTrue(
            any(
                section["start_line"] <= start
                and section["end_line"] >= node.end_lineno
                for section in sections
            ),
            f"{name} was split despite fitting within the limit",
        )

    def test_fitting_function_stays_together(self):
        source = (
            "# padding to move the function near a boundary\n" * 5
            + "def calculate(values):\n"
            + "    total = 0\n"
            + "    for value in values:\n"
            + "        total += value\n"
            + "    return total\n"
        )
        sections = make_sections(source, max_chars=400)
        self.assert_coverage(source, sections, 400)
        self.assert_function_together(source, sections, "calculate")

    def test_method_with_multiline_sql_stays_together(self):
        source = (
            "# padding to move the method near a boundary\n" * 5
            + "class Reports:\n"
            + "    def sales(self):\n"
            + '        query = """SELECT total\n'
            + "FROM orders\n"
            + "WHERE status != 'cancelled'\n"
            + '"""\n'
            + "        return query\n"
        )
        sections = make_sections(source, max_chars=400)
        self.assert_coverage(source, sections, 400)
        self.assert_function_together(source, sections, "sales")

    def test_oversized_function_retains_every_line(self):
        source = (
            "def large_function():\n"
            + "".join(f"    value_{i} = {i}\n" for i in range(100))
        )
        sections = make_sections(
            source, max_chars=400, overlap_lines=3
        )
        self.assertGreater(len(sections), 1)
        self.assert_coverage(source, sections, 400)
        self.assertTrue(
            any(section.get("partial_function") for section in sections)
        )


if __name__ == "__main__":
    unittest.main()
