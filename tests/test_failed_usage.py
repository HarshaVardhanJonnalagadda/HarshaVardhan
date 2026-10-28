"""Offline tests for usage recorded on failed provider calls."""

import json
from pathlib import Path
import tempfile
import unittest

from evidence_store import save_call_failure
from provider import ProviderError, parse_response


class FailedUsageTests(unittest.TestCase):
    def saved_usage(self, error):
        with tempfile.TemporaryDirectory() as folder:
            save_call_failure(folder, "check", error)
            path = Path(folder) / "check_metadata.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["outcome"], "failed")
            return data["usage"]

    def test_truncated_response_preserves_available_usage(self):
        raw = json.dumps({
            "choices": [{
                "message": {"content": "TEST partial response"},
                "finish_reason": "length",
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 2500,
                "total_tokens": 2600,
            },
        })
        with self.assertRaises(ProviderError) as caught:
            parse_response(raw)

        self.assertEqual(self.saved_usage(caught.exception), {
            "input_tokens": 100,
            "output_tokens": 2500,
            "total_tokens": 2600,
        })

    def test_absent_usage_remains_unknown(self):
        usage = self.saved_usage(ProviderError("TEST failure"))
        self.assertTrue(
            all(value == "unknown" for value in usage.values())
        )

    def test_invalid_counts_are_not_accepted(self):
        error = ProviderError(
            "TEST failure",
            raw_response=json.dumps({
                "usage": {
                    "prompt_tokens": True,
                    "completion_tokens": -1,
                    "total_tokens": "15",
                }
            }),
        )
        usage = self.saved_usage(error)
        self.assertTrue(
            all(value == "unknown" for value in usage.values())
        )


if __name__ == "__main__":
    unittest.main()
