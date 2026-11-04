"""Regression coverage for explicitly requested cross-file evidence."""
import tempfile
from pathlib import Path
import unittest

from review_repository import MAX_CONTEXT_CHARS, search


class RepositoryRetrievalTests(unittest.TestCase):
    def test_named_files_and_error_definition_beat_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'reviewer.py').write_text(
                'from provider import call_model, ProviderError\n'
                'def review():\n'
                '    try:\n        return call_model()\n'
                '    except ProviderError:\n        return 1\n'
            )
            (root / 'provider.py').write_text(
                'class ProviderError(RuntimeError):\n    pass\n'
                'def call_model():\n    raise ProviderError("API error")\n'
            )
            (root / 'examples').mkdir()
            (root / 'examples/reviewer_candidate.py').write_text(
                'def review():\n' + '    # API error reviewer provider\n' * 500
                + '    return "unrelated SDK"\n'
            )
            events = []
            context = search(root, 'How does reviewer.py handle an API error '
                             'raised by provider.py?', events)
            self.assertIn('from provider import call_model, ProviderError', context)
            self.assertIn('class ProviderError(RuntimeError)', context)
            self.assertIn('def call_model()', context)
            self.assertIn('except ProviderError:', context)
            self.assertLess(context.index('reviewer.py\n'),
                            context.find('examples/') if 'examples/' in context else len(context))
            self.assertLessEqual(len(context), MAX_CONTEXT_CHARS)
            self.assertEqual(events[-1]['event'], 'selection')

    def test_current_project_error_path_is_retrieved(self):
        root = Path(__file__).resolve().parents[1]
        context = search(root, 'How does reviewer.py handle an API error '
                         'raised by provider.py?', [])
        for expression in ('def review(args)', 'def call_model(',
                           'class ProviderError', 'def save_call_failure('):
            self.assertIn(expression, context)
        self.assertNotIn('examples/reviewer_candidate.py\n', context)


if __name__ == '__main__':
    unittest.main()
