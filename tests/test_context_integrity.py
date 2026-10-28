"""Offline tests for related source retrieval and evidence boundaries."""

import unittest

from verification_context import build_verification_context
from verification_plan import source_batches


SOURCE = """\
def submit(value):
    return process(value)

def process(value):
    return validate(value)

def validate(value):
    if value <= 0:
        raise ValueError("Must be positive")
    return value

def unrelated():
    return "not needed"
"""


class ContextIntegrityTests(unittest.TestCase):
    def test_distant_validation_is_retrieved_together(self):
        result = build_verification_context(
            SOURCE, "Check submit for invalid input."
        )
        names = {block["name"] for block in result["contexts"]}

        self.assertTrue({"submit", "process", "validate"} <= names)
        self.assertNotIn("unrelated", names)

        batches = source_batches(result["contexts"])
        self.assertEqual(len(batches), 1)
        self.assertIn("def submit", batches[0])
        self.assertIn("def validate", batches[0])
        self.assertIn('raise ValueError("Must be positive")', batches[0])

    def test_oversized_evidence_is_not_split(self):
        blocks = [{
            "name": "example",
            "context": "0001: " + "x" * 200,
        }]

        with self.assertRaises(ValueError):
            source_batches(blocks, max_chars=100)

    def test_dependency_depth_limit_is_reported(self):
        result = build_verification_context(
            SOURCE,
            "Check submit.",
            include_callers=False,
            max_depth=1,
        )
        names = {block["name"] for block in result["contexts"]}

        self.assertIn("process", names)
        self.assertNotIn("validate", names)
        self.assertTrue(
            any(
                "depth limit" in limitation
                for limitation in result["limitations"]
            )
        )


if __name__ == "__main__":
    unittest.main()