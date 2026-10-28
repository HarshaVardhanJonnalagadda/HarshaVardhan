"""Resume an incomplete consolidation without repeating successful merges."""

import argparse
import json
from pathlib import Path
import sys
import time
import uuid

from consolidate import SYSTEM
from provider import build_payload, call_model, ProviderError
from evidence_store import (
    save_call_input,
    save_call_success,
    save_call_failure,
    save_json,
    save_text,
    total_usage,
)


def resume(previous):
    previous = Path(previous)
    run = previous.parent

    run_meta = json.loads(
        (run / "metadata.json").read_text(encoding="utf-8")
    )
    if run_meta["outcome"] != "sections_complete":
        raise ValueError("The source section review is incomplete.")

    count = run_meta["expected_sections"]
    draft = ""
    completed = 0
    earlier_results = []

    # Recover only contiguous, successfully completed merges.
    for index in range(1, count + 1):
        name = f"merge_{index:03d}"
        meta_path = previous / f"{name}_metadata.json"

        if not meta_path.exists():
            break

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["outcome"] != "response_complete":
            break

        draft = (previous / f"{name}_response.md").read_text(
            encoding="utf-8"
        )
        earlier_results.append({"usage": meta["usage"]})
        completed = index

    if completed == count:
        raise ValueError("All merges already completed; inspect that folder.")

    request = (run / "request.txt").read_text(encoding="utf-8")
    rules = (run / "rules.txt").read_text(encoding="utf-8")

    output = run / f"consolidation_resume_{uuid.uuid4().hex}"
    output.mkdir(exist_ok=False)

    print(f"New evidence: {output}", flush=True)
    print(f"Reusing {completed} completed merges.", flush=True)

    save_text(output, "recovered_draft.md", draft)
    results = []
    outcome = "failed"
    error = None
    started = time.monotonic()

    try:
        for index in range(completed + 1, count + 1):
            name = f"merge_{index:03d}"
            note = (run / f"section_{index:03d}_response.md").read_text(
                encoding="utf-8"
            )

            context = json.dumps({
                "request": request,
                "business_rules": rules,
                "previous_draft": draft,
                "next_section_notes": note,
                "sections_processed_after_this_call": index,
                "total_sections": count,
            }, ensure_ascii=False)

            if len(context) > 18000:
                raise ValueError(
                    "Input exceeds the character guard; no text was truncated."
                )

            instructions = SYSTEM + (
                "\nKeep the entire updated report under 700 words. "
                "Prioritize the original request. Keep other findings brief. "
                "Preserve important evidence, line references and uncertainty."
            )

            payload = build_payload([
                {"role": "system", "content": instructions},
                {"role": "user", "content": context},
            ], model=run_meta["model"], max_tokens=3500)

            save_call_input(output, name, payload, context)

            print(f"Waiting 65s before merge {index}/{count}...", flush=True)
            time.sleep(65)

            try:
                result = call_model(payload)
            except ProviderError as exc:
                save_call_failure(output, name, exc)
                raise

            save_call_success(output, name, result)
            results.append(result)
            draft = result["text"]
            print(f"Merge {index}/{count} saved.", flush=True)

        save_text(output, "review.md", draft)
        outcome = "consolidation_complete"

    except (ProviderError, ValueError, OSError) as exc:
        error = str(exc)

    except KeyboardInterrupt:
        outcome = "interrupted"
        error = "Stopped by user."

    finally:
        save_json(output, "metadata.json", {
            "provider": "Groq",
            "model": run_meta["model"],
            "outcome": outcome,
            "resumed_from": str(previous),
            "reused_merges": completed,
            "successful_new_merges": len(results),
            "expected_total_merges": count,
            "duration_seconds": round(time.monotonic() - started, 3),
            "new_usage_totals": total_usage(results),
            "successful_merge_usage_totals": total_usage(
                earlier_results + results
            ),
            "usage_scope": (
                "Successful merges only. Failed attempts and original "
                "section reviews have separate evidence and usage."
            ),
            "human_validation": "pending",
            "original_source_supplied_to_consolidator": False,
            "error": error,
        })

    if error:
        raise ValueError(f"{error} Evidence: {output}")

    print(f"Final report saved: {output / 'review.md'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous_consolidation")
    args = parser.parse_args()

    try:
        resume(args.previous_consolidation)
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())