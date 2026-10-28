"""Offline consolidation tests. No live API calls."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from consolidate import consolidate
from provider import ProviderError


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

        self.write_json("metadata.json", {
            "outcome": "sections_complete",
            "expected_sections": 2,
            "model": "test-model",
        })

        self.write("request.txt", "Review this code for bugs")
        self.write("rules.txt", "No business rules supplied.")
        self.write("section_001_response.md", "TEST section one notes")
        self.write("section_002_response.md", "TEST section two notes")

    def write(self, name, text):
        (self.folder / name).write_text(text, encoding="utf-8")

    def write_json(self, name, data):
        self.write(name, json.dumps(data))

    def result(self):
        return {
            "text": "TEST FIXTURE: consolidated report",
            "raw_response": json.dumps({"test_fixture": True}),
            "duration_seconds": 0.01,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }

    def test_success_saves_report_and_evidence(self):
        with patch(
            "consolidate.call_model",
            return_value=self.result(),
        ) as model:
            report = consolidate(self.folder, pause=0)

        self.assertTrue(report.exists())
        self.assertEqual(model.call_count, 2)

        metadata = json.loads(
            (report.parent / "metadata.json").read_text()
        )
        self.assertEqual(
            metadata["outcome"], "consolidation_complete"
        )
        self.assertEqual(
            metadata["usage_totals"]["total_tokens"], 30
        )
        self.assertTrue(
            (report.parent / "merge_001_prompt.json").exists()
        )
        self.assertTrue(
            (report.parent / "merge_002_raw_response.json").exists()
        )

        second_payload = model.call_args_list[1].args[0]
        second_input = json.loads(
            second_payload["messages"][1]["content"]
        )
        self.assertEqual(
            second_input["previous_draft"],
            "TEST FIXTURE: consolidated report",
        )

    def test_failed_sections_are_rejected(self):
        self.write_json("metadata.json", {
            "outcome": "failed",
            "expected_sections": 2,
            "model": "test-model",
        })

        with patch("consolidate.call_model") as model:
            with self.assertRaises(ValueError):
                consolidate(self.folder, pause=0)
            model.assert_not_called()

    def test_provider_failure_produces_no_final_report(self):
        with patch(
            "consolidate.call_model",
            side_effect=ProviderError("TEST quota failure"),
        ):
            with self.assertRaises(ValueError):
                consolidate(self.folder, pause=0)

        output = next(self.folder.glob("consolidation_*"))
        self.assertFalse((output / "review.md").exists())

        metadata = json.loads(
            (output / "metadata.json").read_text()
        )
        self.assertEqual(metadata["outcome"], "failed")

    def test_oversized_input_is_not_silently_truncated(self):
        self.write("section_001_response.md", "x" * 19000)

        with patch("consolidate.call_model") as model:
            with self.assertRaises(ValueError):
                consolidate(self.folder, pause=0)
            model.assert_not_called()


if __name__ == "__main__":
    unittest.main()