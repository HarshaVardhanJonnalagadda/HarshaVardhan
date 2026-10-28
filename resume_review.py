"""Resume saved reviews with token checks and preserved API evidence."""

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import tiktoken

import reviewer
from provider import parse_response


def without_output_limit(payload):
    return {
        key: value
        for key, value in payload.items()
        if key != "max_completion_tokens"
    }


def resume(args):
    if args.pause < 0 or args.timeout <= 0:
        raise ValueError("Pause must be nonnegative and timeout positive.")

    previous = Path(args.run_folder)
    metadata = json.loads(
        (previous / "metadata.json").read_text(encoding="utf-8")
    )

    if metadata.get("outcome") not in (
        "failed", "interrupted", "sections_complete"
    ):
        raise ValueError("This run is not eligible for resuming.")

    if metadata["model"] != "openai/gpt-oss-120b":
        raise ValueError(
            "This tokenizer and budget configuration supports "
            "openai/gpt-oss-120b."
        )

    request = (previous / "request.txt").read_text(encoding="utf-8")
    rules = (previous / "rules.txt").read_text(encoding="utf-8")
    snapshot = (previous / "source_snapshot.py").read_text(
        encoding="utf-8"
    )

    source = reviewer.load_source(args.source)
    if source["text"] != snapshot:
        raise ValueError("Source differs from the saved snapshot.")

    sections = reviewer.make_sections(source["text"])
    if len(sections) != metadata["expected_sections"]:
        raise ValueError("Source section boundaries have changed.")

    original_build = reviewer.build_payload
    encoding = tiktoken.get_encoding("o200k_harmony")
    cached = {}
    prepared = {}

    # Validate reusable results and prepare all missing requests first.
    for index, section in enumerate(sections, 1):
        name = f"section_{index:03d}"
        messages = reviewer.build_messages(
            request, rules or None, section, len(sections)
        )
        expected = original_build(messages, metadata["model"])

        status_path = previous / f"{name}_metadata.json"
        status = (
            json.loads(status_path.read_text(encoding="utf-8"))
            if status_path.exists()
            else {}
        )

        prompt_path = previous / f"{name}_prompt.json"
        saved_payload = (
            json.loads(prompt_path.read_text(encoding="utf-8"))
            if prompt_path.exists()
            else None
        )

        if status.get("outcome") == "response_complete":
            if (
                saved_payload is None
                or without_output_limit(saved_payload)
                != without_output_limit(expected)
            ):
                raise ValueError(
                    f"{name}: saved messages or model settings changed. "
                    "Cannot safely reuse the response."
                )

            raw = (previous / f"{name}_raw_response.json").read_text(
                encoding="utf-8"
            )
            result = parse_response(raw)
            result["duration_seconds"] = status.get("duration_seconds")

            cached[index] = result
            prepared[index] = saved_payload
            print(f"Section {index}: validated saved success.", flush=True)
            continue

        desired_output = expected["max_completion_tokens"]
        truncated = False
        raw_path = previous / f"{name}_raw_response.json"

        if raw_path.exists():
            try:
                raw_data = json.loads(
                    raw_path.read_text(encoding="utf-8")
                )
                choices = raw_data.get("choices") or [{}]
                truncated = choices[0].get("finish_reason") == "length"
            except (ValueError, AttributeError, TypeError, IndexError):
                pass

        if truncated:
            if (
                saved_payload is None
                or without_output_limit(saved_payload)
                != without_output_limit(expected)
            ):
                raise ValueError(
                    f"{name}: incomplete response belongs to a "
                    "different prompt or configuration."
                )
            old_limit = saved_payload["max_completion_tokens"]
            desired_output = old_limit + 1500

        content_tokens = sum(
            len(encoding.encode(
                message["content"], disallowed_special=()
            ))
            for message in messages
        )

        # Reserve 500 estimated tokens for message-format overhead.
        available_output = args.token_limit - content_tokens - 500

        if available_output < desired_output:
            raise ValueError(
                f"Section {index}: needs an estimated "
                f"{content_tokens + desired_output + 500} tokens "
                f"including output and margin; limit is "
                f"{args.token_limit}. No API calls were made. "
                "Source and output were not silently shortened."
            )

        payload = copy.deepcopy(expected)
        payload["max_completion_tokens"] = desired_output
        prepared[index] = payload

        print(
            f"Section {index}: new call; content={content_tokens}, "
            f"output allowance={desired_output}, "
            f"estimated total={content_tokens + desired_output + 500}.",
            flush=True,
        )

    print(
        f"Validated {len(cached)} reusable sections "
        f"out of {len(sections)}.",
        flush=True,
    )

    if args.check_only:
        print("Check complete. No API calls or file changes made.")
        return 0

    if len(cached) < len(sections):
        if not os.environ.get("GROQ_API_KEY", "").strip():
            raise ValueError(
                "GROQ_API_KEY is not set in this terminal."
            )

    original_call = reviewer.call_model
    original_create = reviewer.create_run
    build_index = 0
    call_index = 0

    def build_prepared(*values, **options):
        nonlocal build_index
        build_index += 1

        current = original_build(*values, **options)
        payload = prepared[build_index]

        if without_output_limit(current) != without_output_limit(payload):
            raise ValueError("Prompt changed after preflight.")

        # reviewer saves this exact payload before calling the model.
        return copy.deepcopy(payload)

    def create_linked_run(*values, **options):
        folder = original_create(*values, **options)
        reviewer.save_json(folder, "resume_info.json", {
            "previous_run": str(previous.resolve()),
            "reused_sections": sorted(cached),
            "token_limit": args.token_limit,
            "overhead_margin": 500,
            "token_accounting": (
                "Local estimate; provider accounting may differ."
            ),
            "usage_note": (
                "Run totals include reused historical results. "
                "Do not add totals across resume folders because "
                "that would count reused calls more than once."
            ),
        })
        return folder

    def reuse_or_call(payload, timeout=120):
        nonlocal call_index
        call_index += 1

        if call_index in cached:
            print(
                f"Reusing saved section {call_index}; no API call.",
                flush=True,
            )
            return copy.deepcopy(cached[call_index])

        if args.pause:
            print(
                f"Waiting {args.pause:g}s before new API call...",
                flush=True,
            )
            time.sleep(args.pause)

        return original_call(payload, timeout=timeout)

    run_args = argparse.Namespace(
        source=args.source,
        request=None,
        request_file=str(previous / "request.txt"),
        rules=str(previous / "rules.txt") if rules.strip() else None,
        output=str(previous.parent),
        model=metadata["model"],
        timeout=args.timeout,
        pause=0,
        dry_run=False,
    )

    with patch.object(reviewer, "build_payload", build_prepared):
        with patch.object(reviewer, "call_model", reuse_or_call):
            with patch.object(reviewer, "create_run", create_linked_run):
                return reviewer.review(run_args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder")
    parser.add_argument("source")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--pause", type=float, default=65)
    parser.add_argument("--token-limit", type=int, default=8000)
    args = parser.parse_args()

    try:
        return resume(args)
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())