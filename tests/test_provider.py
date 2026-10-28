"""Provider tests using simulated HTTP responses; no live API calls."""

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from provider import ProviderError, call_model, parse_response


class ProviderTests(unittest.TestCase):
    def test_successful_http_response(self):
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
        }).encode("utf-8")

        with patch.dict(
            "os.environ", {"GROQ_API_KEY": "test-placeholder"}, clear=True
        ):
            with patch("provider.urllib.request.urlopen") as open_url:
                open_url.return_value.__enter__.return_value.read.return_value = raw
                result = call_model({"model": "test-model"}, timeout=3)

        self.assertEqual(result["text"], "TEST FIXTURE ONLY")
        self.assertEqual(result["usage"]["total_tokens"], 15)
        self.assertGreaterEqual(result["duration_seconds"], 0)
        self.assertNotIn("test-placeholder", result["raw_response"])
        self.assertEqual(open_url.call_args.kwargs["timeout"], 3)

    def test_missing_key_prevents_network_call(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("provider.urllib.request.urlopen") as open_url:
                with self.assertRaisesRegex(ProviderError, "not set"):
                    call_model({})
                open_url.assert_not_called()

    def test_http_error_redacts_key_and_preserves_retry_hint(self):
        key = "test-secret-placeholder"
        body = json.dumps({
            "error": {
                "message": f"Quota exceeded for {key}",
                "type": "rate_limit_error",
            }
        }).encode("utf-8")

        error = urllib.error.HTTPError(
            "https://example.invalid",
            429,
            "Too Many Requests",
            {"retry-after": "65"},
            io.BytesIO(body),
        )

        with patch.dict("os.environ", {"GROQ_API_KEY": key}, clear=True):
            with patch(
                "provider.urllib.request.urlopen", side_effect=error
            ):
                with self.assertRaises(ProviderError) as caught:
                    call_model({})

        failure = caught.exception
        self.assertIn("429", str(failure))
        self.assertNotIn(key, str(failure))
        self.assertNotIn(key, failure.raw_response)
        details = json.loads(failure.raw_response)
        self.assertEqual(details["rate_limit_headers"]["retry-after"], "65")

    def test_connection_failure_is_provider_error(self):
        with patch.dict(
            "os.environ", {"GROQ_API_KEY": "test-placeholder"}, clear=True
        ):
            with patch(
                "provider.urllib.request.urlopen",
                side_effect=urllib.error.URLError("TEST connection failure"),
            ):
                with self.assertRaisesRegex(ProviderError, "Connection failed"):
                    call_model({})

    def test_malformed_response_preserves_raw_evidence(self):
        raw = '{"choices": null}'
        with self.assertRaises(ProviderError) as caught:
            parse_response(raw)
        self.assertEqual(caught.exception.raw_response, raw)

    def test_invalid_usage_counts_remain_unknown(self):
        raw = json.dumps({
            "choices": [{
                "message": {"content": "TEST FIXTURE ONLY"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": True,
                "completion_tokens": -1,
                "total_tokens": "15",
            },
        })

        result = parse_response(raw)
        self.assertEqual(result["usage"], {
            "input_tokens": "unknown",
            "output_tokens": "unknown",
            "total_tokens": "unknown",
        })


if __name__ == "__main__":
    unittest.main()
