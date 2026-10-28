"""Offline tests for incomplete-function context in review prompts."""

import json
import unittest

from prompts import build_messages


class PromptBoundaryTests(unittest.TestCase):
    def section(self):
        return {
            "section": 1,
            "start_line": 1,
            "end_line": 1,
            "context": "0001: value = 1\n",
        }

    def test_explicit_flags_are_preserved(self):
        for flag in (True, False):
            with self.subTest(flag=flag):
                section = self.section()
                section["partial_function"] = flag
                messages = build_messages("Review this code.", None, section, 1)
                data = json.loads(messages[1]["content"])
                self.assertIs(data["partial_function"], flag)

    def test_missing_flag_defaults_to_caution(self):
        messages = build_messages(
            "Review this code.", None, self.section(), 1
        )
        data = json.loads(messages[1]["content"])
        self.assertIs(data["partial_function"], True)

    def test_source_context_is_unchanged(self):
        section = self.section()
        messages = build_messages("Review this code.", None, section, 1)
        data = json.loads(messages[1]["content"])
        self.assertEqual(data["numbered_source"], section["context"])


if __name__ == "__main__":
    unittest.main()
