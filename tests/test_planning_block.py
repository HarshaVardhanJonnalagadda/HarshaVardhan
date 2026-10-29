import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verify_report import verify


class PlanningBlockTests(unittest.TestCase):
    def test_planning_block_prevents_provider_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            folder = run / "verification_test"
            folder.mkdir()

            (run / "run_info.json").write_text(
                json.dumps({"model": "openai/gpt-oss-120b"}),
                encoding="utf-8",
            )
            plan = {
                "request": "Review this code.",
                "rules": "No additional rules.",
                "tasks": [{
                    "finding_id": 1,
                    "finding": "A candidate finding.",
                    "batch": 1,
                    "total_batches": 1,
                    "matched_functions": ["example"],
                    "source_context": "Evidence withheld: task blocked.",
                    "retrieval_limitations": [],
                    "planning_blocked": "Evidence exceeds character limit.",
                }],
            }
            (folder / "plan.json").write_text(
                json.dumps(plan), encoding="utf-8"
            )

            # Even an eligible token estimate must not override the block.
            budget = {
                "estimated_total": 100,
                "limit": 8000,
                "eligible": True,
            }
            with patch(
                "verify_report.token_budget", return_value=budget
            ), patch("verify_report.call_model") as provider:
                summary = verify(folder, pause=0)

            provider.assert_not_called()

            metadata = json.loads(
                (summary / "metadata.json").read_text(encoding="utf-8")
            )
            report = (summary / "verification_report.md").read_text(
                encoding="utf-8"
            )

            self.assertEqual(metadata["outcome"], "verification_incomplete")
            self.assertEqual(metadata["blocked_tasks"], [1])
            self.assertEqual(metadata["successful_tasks"], 0)
            self.assertIn("Evidence exceeds character limit.", report)
            self.assertIn("UNRESOLVED", report)


if __name__ == "__main__":
    unittest.main()