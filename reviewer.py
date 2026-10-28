"""Command-line Python code reviewer."""

import argparse
import hashlib
from pathlib import Path
import sys
import time

from source_context import InputError, load_source, make_sections, read_text_file
from prompts import build_messages
from provider import DEFAULT_MODEL, ProviderError, build_payload, call_model
from evidence_store import (
    create_run,
    save_call_failure,
    save_call_input,
    save_call_success,
    save_json,
    save_text,
    total_usage,
)


def review(args):
    if args.request_file:
        request, _ = read_text_file(args.request_file)
    else:
        request = args.request

    if not request or not request.strip() or "\x00" in request:
        raise InputError("Provide a nonblank request without NUL characters.")

    if args.pause < 0 or args.timeout <= 0:
        raise InputError("Pause must be nonnegative and timeout positive.")

    source = load_source(args.source)

    rules = None
    if args.rules:
        rules, _ = read_text_file(args.rules)

    sections = make_sections(source["text"])
    folder = create_run(
        args.output, source, request, rules, args.model
    )

    print(f"Evidence folder: {folder}", flush=True)
    print(
        f"Source: {source['line_count']} lines, "
        f"{len(sections)} sections",
        flush=True,
    )

    started = time.monotonic()
    results = []
    reports = []
    outcome = "failed"
    failure = None

    try:
        for index, section in enumerate(sections):
            name = f"section_{index + 1:03d}"

            messages = build_messages(
                request, rules, section, len(sections)
            )
            payload = build_payload(messages, args.model)

            save_call_input(
                folder, name, payload, section["context"]
            )

            if args.dry_run:
                print(f"Prepared {name}; no API call.", flush=True)
                continue

            if index > 0 and args.pause:
                print(
                    f"Waiting {args.pause:g} seconds before next call...",
                    flush=True,
                )
                time.sleep(args.pause)

            print(
                f"Reviewing {index + 1}/{len(sections)} "
                f"(lines {section['start_line']}"
                f"-{section['end_line']})...",
                flush=True,
            )

            try:
                result = call_model(payload, timeout=args.timeout)
            except ProviderError as exc:
                save_call_failure(folder, name, exc)
                raise

            save_call_success(folder, name, result)
            results.append(result)

            reports.append(
                f"# Section {index + 1}: original lines "
                f"{section['start_line']}-{section['end_line']}\n\n"
                f"{result['text']}"
            )

        if args.dry_run:
            outcome = "dry_run_no_api_calls"
            save_text(
                folder,
                "status.txt",
                "Prompts prepared only. No model review was produced.\n",
            )
        else:
            outcome = "sections_complete"

    except KeyboardInterrupt:
        outcome = "interrupted"
        failure = "Stopped by user; review is incomplete."

    except ProviderError as exc:
        failure = str(exc)

    except OSError:
        failure = "Could not read or write an evidence file."

    finally:
        try:
            current_hash = hashlib.sha256(
                Path(args.source).read_bytes()
            ).hexdigest()
            source_unchanged = current_hash == source["sha256"]
        except OSError:
            source_unchanged = False

        if not source_unchanged:
            outcome = "failed"
            failure = "Source changed or became unreadable during the run."

        if reports:
            header = (
                "# Section review results\n\n"
                f"Run outcome: {outcome}\n\n"
                "These are separate model reviews of source sections. "
                "They are not a consolidated assessment. Cross-section "
                "behavior may be unresolved and duplicate findings may "
                "appear. Human validation is pending.\n\n"
            )

            save_text(
                folder,
                "section_reviews.md",
                header + "\n\n---\n\n".join(reports),
            )

        save_json(folder, "metadata.json", {
            "provider": "Groq",
            "model": args.model,
            "outcome": outcome,
            "expected_sections": len(sections),
            "successful_sections": len(results),
            "duration_seconds": round(time.monotonic() - started, 3),
            "usage_totals": total_usage(results),
            "usage_scope": (
                "Successfully parsed calls only; failed-call usage "
                "may be unavailable."
            ),
            "source_unchanged": source_unchanged,
            "human_validation": "pending",
            "error": failure,
        })

    if failure:
        print(f"Incomplete: {failure}", file=sys.stderr)
        print(f"Inspect evidence: {folder}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run complete. No API calls made.")
    else:
        print(
            "Section reviews saved. Consolidation and human "
            "validation remain pending."
        )

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request")
    group.add_argument("--request-file")

    parser.add_argument("--rules")
    parser.add_argument("--output", default="reviews")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--pause", type=float, default=65)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    try:
        return review(args)
    except (InputError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())