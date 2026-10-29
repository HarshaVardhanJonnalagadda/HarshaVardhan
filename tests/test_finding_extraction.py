"""Regression tests for extracting candidate finding rows."""

import unittest

from verification_plan import extract_findings


class FindingExtractionTests(unittest.TestCase):
    def test_both_supported_headings(self):
        row = "| High | Incorrect calculation | `calculate` |"
        for heading in ("Findings", "Important findings"):
            with self.subTest(heading=heading):
                report = (
                    f"## {heading}\n"
                    "| Severity | Title | Location |\n"
                    "| --- | --- | --- |\n"
                    f"{row}\n"
                )
                self.assertEqual(extract_findings(report), [row])

    def test_duplicates_and_uncertainty_are_excluded(self):
        row = "| Low | Incorrect result | `calculate` |"
        report = (
            f"## Findings\n{row}\n{row}\n"
            "## Uncertainty\n"
            "| High | Speculative issue | `other` |\n"
        )
        self.assertEqual(extract_findings(report), [row])

    def test_prose_only_report_requires_inspection(self):
        with self.assertRaises(ValueError):
            extract_findings(
                "## Findings\nPossible issue described only in prose.\n"
            )


if __name__ == "__main__":
    unittest.main()
