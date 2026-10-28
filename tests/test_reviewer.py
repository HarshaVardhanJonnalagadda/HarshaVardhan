"""Offline tests. All model replies are test fixtures, not live results."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from source_context import InputError, load_source, make_sections
from provider import ProviderError, parse_response
from evidence_store import save_text, total_usage
import reviewer


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)
        self.source = self.root / "example.py"

        # Reviewing this file must never execute its contents.
        self.source.write_text(
            'raise RuntimeError("SOURCE MUST NOT EXECUTE")\n',
            encoding="utf-8",
        )

        self.args = argparse.Namespace(
            source=str(self.source),
            request="Review this code for bugs",
            request_file=None,
            rules=None,
            output=str(self.root / "reviews"),
            model="test-model",
            timeout=10,
            pause=0,
            dry_run=False,
        )

    def folders(self):
        return list((self.root / "reviews").iterdir())

    def fixture_result(self):
        raw = json.dumps({
            "choices": [{
                "message": {"content": "TEST FIXTURE ONLY"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        })

        result = parse_response(raw)
        result["duration_seconds"] = 0.01
        return result

    def test_success_and_source_preservation(self):
        before = self.source.read_bytes()

        with patch(
            "reviewer.call_model",
            return_value=self.fixture_result(),
        ):
            self.assertEqual(reviewer.review(self.args), 0)

        folder = self.folders()[0]
        metadata = json.loads(
            (folder / "metadata.json").read_text()
        )

        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(metadata["source_unchanged"])
        self.assertEqual(metadata["outcome"], "sections_complete")
        self.assertEqual(metadata["usage_totals"]["total_tokens"], 15)
        self.assertTrue((folder / "section_001_prompt.json").exists())
        self.assertTrue((folder / "section_001_context.txt").exists())
        self.assertTrue((folder / "section_001_raw_response.json").exists())
        self.assertTrue((folder / "section_reviews.md").exists())

    def test_dry_run_never_calls_provider(self):
        self.args.dry_run = True

        with patch("reviewer.call_model") as mock:
            self.assertEqual(reviewer.review(self.args), 0)
            mock.assert_not_called()

        metadata = json.loads(
            (self.folders()[0] / "metadata.json").read_text()
        )
        self.assertEqual(metadata["outcome"], "dry_run_no_api_calls")

    def test_provider_failure_is_not_success(self):
        with patch(
            "reviewer.call_model",
            side_effect=ProviderError("TEST HTTP 429"),
        ):
            self.assertEqual(reviewer.review(self.args), 1)

        folder = self.folders()[0]
        metadata = json.loads(
            (folder / "metadata.json").read_text()
        )

        self.assertEqual(metadata["outcome"], "failed")
        self.assertEqual(metadata["successful_sections"], 0)
        self.assertFalse((folder / "section_reviews.md").exists())
        self.assertTrue((folder / "section_001_metadata.json").exists())

    def test_blank_request(self):
        self.args.request = "   "

        with self.assertRaises(InputError):
            reviewer.review(self.args)

    def test_missing_and_unreadable_source(self):
        with self.assertRaises(InputError):
            load_source(self.root / "missing.py")

        with patch(
            "pathlib.Path.read_bytes",
            side_effect=PermissionError("TEST permission denied"),
        ):
            with self.assertRaises(InputError):
                load_source(self.source)

    def test_invalid_text_and_python(self):
        for content in (b"\xff", b"", b"x = \x00", b"def broken("):
            with self.subTest(content=content):
                self.source.write_bytes(content)

                with self.assertRaises(InputError):
                    load_source(self.source)

    def test_sections_cover_all_lines(self):
        text = "".join(f"value_{i} = {i}\n" for i in range(200))
        sections = make_sections(
            text, max_chars=500, overlap_lines=3
        )

        covered = {
            line
            for section in sections
            for line in range(
                section["start_line"], section["end_line"] + 1
            )
        }

        self.assertEqual(covered, set(range(1, 201)))
        self.assertTrue(
            all(len(s["context"]) <= 500 for s in sections)
        )

    def test_empty_malformed_and_truncated_responses(self):
        responses = [
            "not JSON",
            "{}",
            json.dumps({
                "choices": [{
                    "message": {"content": ""},
                    "finish_reason": "stop",
                }],
            }),
            json.dumps({
                "choices": [{
                    "message": {"content": "Partial answer"},
                    "finish_reason": "length",
                }],
            }),
        ]

        for raw in responses:
            with self.subTest(raw=raw):
                with self.assertRaises(ProviderError):
                    parse_response(raw)

    def test_no_overwriting(self):
        save_text(self.root, "existing.txt", "original")

        with self.assertRaises(FileExistsError):
            save_text(self.root, "existing.txt", "replacement")

        self.assertEqual(
            (self.root / "existing.txt").read_text(),
            "original",
        )

    def test_unknown_usage_stays_unknown(self):
        result = {
            "usage": {
                "input_tokens": "unknown",
                "output_tokens": 5,
                "total_tokens": "unknown",
            },
        }

        self.assertEqual(
            total_usage([result])["total_tokens"],
            "unknown",
        )

    def test_source_hash_matches_original_bytes(self):
        source = load_source(self.source)

        self.assertEqual(
            source["sha256"],
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
        )

    def test_each_run_has_a_unique_folder(self):
        self.args.dry_run = True
        reviewer.review(self.args)
        reviewer.review(self.args)

        self.assertEqual(len(self.folders()), 2)


if __name__ == "__main__":
    unittest.main()