"""Offline verification and resume test."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verify_report import verify


class VerificationTests(unittest.TestCase):
    def test_saved_success_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            folder = run / "verification_test"
            folder.mkdir()

            (run / "run_info.json").write_text(
                json.dumps({"model": "openai/gpt-oss-120b"})
            )
            (folder / "plan.json").write_text(json.dumps({
                "request": "Review this code",
                "rules": "No rules supplied",
                "tasks": [{
                    "finding_id": 1,
                    "finding": "TEST claim",
                    "batch": 1,
                    "total_batches": 1,
                    "source_context": "0001: value = 1\n",
                }],
            }))

            fixture = {
                "text": "TEST FIXTURE: unresolved",
                "raw_response": '{"test_fixture": true}',
                "duration_seconds": 0.01,
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            }

            with patch(
                "verify_report.call_model", return_value=fixture
            ) as model:
                first = verify(folder, pause=0)
                self.assertEqual(model.call_count, 1)
                self.assertTrue(
                    (first / "verification_report.md").exists()
                )

            with patch("verify_report.call_model") as model:
                verify(folder, pause=0)
                model.assert_not_called()


if __name__ == "__main__":
    unittest.main()