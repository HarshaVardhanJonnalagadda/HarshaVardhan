"""Groq API connection with sanitized failure diagnostics."""

import json
import os
import time
import urllib.error
import urllib.request


API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"


class ProviderError(RuntimeError):
    """A failed API call, with available evidence attached."""

    def __init__(self, message, raw_response=None, duration_seconds=None):
        super().__init__(message)
        self.raw_response = raw_response
        self.duration_seconds = duration_seconds


def build_payload(messages, model=DEFAULT_MODEL, max_tokens=2500):
    if not messages:
        raise ValueError("Messages must not be empty.")

    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive.")

    return {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_completion_tokens": max_tokens,
    }


def parse_response(raw):
    try:
        data = json.loads(raw)
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError(
            "Provider returned a malformed response.",
            raw_response=raw,
        ) from None

    if not isinstance(content, str) or not content.strip():
        raise ProviderError(
            "Provider returned an empty response.",
            raw_response=raw,
        )

    if choice.get("finish_reason") != "stop":
        raise ProviderError(
            "Response was incomplete or its completion status was unknown.",
            raw_response=raw,
        )

    usage = data.get("usage")
    if not isinstance(usage, dict):
        usage = {}

    def token_count(name):
        value = usage.get(name)
        if type(value) is int and value >= 0:
            return value
        return "unknown"

    return {
        "text": content,
        "raw_response": raw,
        "usage": {
            "input_tokens": token_count("prompt_tokens"),
            "output_tokens": token_count("completion_tokens"),
            "total_tokens": token_count("total_tokens"),
        },
    }


def call_model(payload, timeout=120):
    key = os.environ.get("GROQ_API_KEY", "").strip()

    if not key:
        raise ProviderError("GROQ_API_KEY is not set.")

    if timeout <= 0:
        raise ValueError("Timeout must be positive.")

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "CodeReviewAgent/1.0",
        },
        method="POST",
    )

    started = time.monotonic()

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")

    except urllib.error.HTTPError as exc:
        hints = {
            400: "Check the model and request parameters.",
            401: "Check your Groq API key.",
            403: "Check account permissions.",
            413: "The request is too large.",
            429: "Rate limit or quota reached.",
        }
        hint = hints.get(exc.code, "Check provider availability.")

        def redact(value):
            return str(value).replace(key, "[REDACTED]")

        details = {
            "http_status": exc.code,
            "message": hint,
            "rate_limit_headers": {},
        }

        # Save selected error fields, excluding request credentials.
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            error = parsed.get("error", {}) if isinstance(parsed, dict) else {}

            if isinstance(error, dict):
                for field in ("message", "type", "code"):
                    value = error.get(field)
                    if isinstance(value, (str, int, float)):
                        details[field] = redact(value)[:2000]
        except (ValueError, AttributeError, OSError):
            pass

        if exc.headers:
            for name, value in exc.headers.items():
                lower = name.lower()
                if lower == "retry-after" or lower.startswith("x-ratelimit-"):
                    details["rate_limit_headers"][lower] = redact(value)[:500]

        message = f"Groq HTTP {exc.code}: {details['message']}"
        if details["rate_limit_headers"]:
            message += " | Limit details: " + json.dumps(
                details["rate_limit_headers"]
            )

        raise ProviderError(
            message,
            raw_response=json.dumps(details, ensure_ascii=False),
            duration_seconds=round(time.monotonic() - started, 3),
        ) from None

    except (urllib.error.URLError, OSError, TimeoutError, UnicodeError):
        raise ProviderError(
            "Connection failed, timed out, or returned invalid text.",
            duration_seconds=round(time.monotonic() - started, 3),
        ) from None

    duration = round(time.monotonic() - started, 3)

    try:
        result = parse_response(raw)
    except ProviderError as exc:
        exc.duration_seconds = duration
        raise

    result["duration_seconds"] = duration
    return result