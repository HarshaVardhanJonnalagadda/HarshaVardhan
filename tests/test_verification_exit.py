"""Offline regression tests for verification CLI exit status."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import verify_report


class VerificationExitTests(unittest.TestCase):
    def run_with_outcome(self, outcome):
        with tempfile.TemporaryDirectory() as temp:
            summary = Path(temp)
            (summary / "metadata.json").write_text(
                json.dumps({"outcome": outcome}),
                encoding="utf-8",
            )

            with patch.object(
                verify_report, "verify", return_value=summary
            ):
                with patch(
                    "sys.argv", ["verify_report.py", "test-folder"]
                ):
                    return verify_report.main()

    def test_complete_verification_returns_zero(self):
        self.assertEqual(
            self.run_with_outcome("verification_calls_complete"), 0
        )

    def test_incomplete_verification_returns_nonzero(self):
        self.assertEqual(
            self.run_with_outcome("verification_incomplete"), 1
        )

    def test_dry_run_needs_no_summary_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(
                verify_report, "verify", return_value=Path(temp)
            ) as mocked:
                with patch(
                    "sys.argv",
                    ["verify_report.py", "test-folder", "--dry-run"],
                ):
                    self.assertEqual(verify_report.main(), 0)

                self.assertTrue(mocked.call_args.kwargs["dry_run"])


if __name__ == "__main__":
    unittest.main()
