"""Prepare source-verification requests without calling an API."""

import argparse
import json
from pathlib import Path
import re
import sys
import uuid

from source_context import load_source
from verification_context import build_verification_context


def extract_findings(report):
    """Extract finding rows from the Important findings Markdown table."""
    findings = []
    in_findings = False

    for line in report.splitlines():
        heading = line.strip().lstrip("*").strip()

        if heading.startswith("## Important findings"):
            in_findings = True
            continue

        if in_findings and heading.startswith("## "):
            break

        if not in_findings:
            continue

        row = line.strip().replace("\\|", "|")
        if not row.startswith("|"):
            continue

        cells = [cell.strip() for cell in row.strip("|").split("|")]

        if len(cells) < 3:
            continue

        first = cells[0].replace("*", "").strip().lower()
        if first == "severity" or re.fullmatch(r"[-:\s]+", first):
            continue

        findings.append(line.strip())

    if not findings:
        raise ValueError(
            "No finding rows found. The report format needs inspection."
        )

    return findings


def source_batches(contexts, max_chars=30000):
    """Keep related evidence together; never split or truncate it."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")

    blocks = [
        f"\nSOURCE BLOCK: {block['name']}\n{block['context']}"
        for block in contexts
    ]

    combined = "\n".join(blocks)

    if not combined.strip():
        return []

    if len(combined) > max_chars:
        raise ValueError(
            f"Related source context is {len(combined)} characters; "
            f"the limit is {max_chars}. Planning stopped without "
            "API calls. No source was split or truncated. "
            "A strategy for larger evidence sets is required."
        )

    return [combined]


def find_run_folder(report_path):
    """Find the ancestor containing the original review evidence."""
    for folder in report_path.parents:
        required = (
            "source_snapshot.py",
            "request.txt",
            "rules.txt",
        )
        if all((folder / name).is_file() for name in required):
            return folder

    raise ValueError(
        "Cannot locate source_snapshot.py, request.txt and rules.txt "
        "in the report's parent folders."
    )


def prepare(report_path):
    report_path = Path(report_path).resolve()

    if not report_path.is_file():
        raise ValueError(f"Report file not found: {report_path}")

    run = find_run_folder(report_path)

    source = load_source(run / "source_snapshot.py")
    report = report_path.read_text(encoding="utf-8")
    request = (run / "request.txt").read_text(encoding="utf-8")
    rules = (run / "rules.txt").read_text(encoding="utf-8")

    findings = extract_findings(report)
    tasks = []

    # Prepare every task before creating the output folder.
    # If any evidence set is too large, stop without API calls.
    for index, finding in enumerate(findings, 1):
        retrieved = build_verification_context(
            source["text"],
            finding,
            include_callers=True,
        )

        limitations = list(retrieved["limitations"])

        if not retrieved["matched_functions"]:
            contexts = []
            limitations.append(
                "No functions matched this finding. "
                "It must remain unresolved until relevant source "
                "is identified."
            )
        else:
            contexts = retrieved["contexts"]

        try:
            batches = source_batches(contexts)
        except ValueError as exc:
            raise ValueError(f"Finding {index}: {exc}") from None

        if not batches:
            batches = [
                "No matching function context was retrieved. "
                "This finding must remain unresolved."
            ]

        for batch_index, context in enumerate(batches, 1):
            tasks.append({
                "finding_id": index,
                "finding": finding,
                "batch": batch_index,
                "total_batches": len(batches),
                "matched_functions": retrieved["matched_functions"],
                "source_context": context,
                "retrieval_limitations": limitations,
            })

    output = run / f"verification_{uuid.uuid4().hex}"
    output.mkdir(exist_ok=False)

    plan = {
        "report_path": str(report_path),
        "source_sha256": source["sha256"],
        "request": request,
        "rules": rules,
        "finding_count": len(findings),
        "tasks": tasks,
        "status": "prepared_no_api_calls",
        "context_policy": (
            "Retrieved evidence for each finding stays together. "
            "Oversized evidence stops planning; it is never split "
            "or truncated."
        ),
    }

    with (output / "plan.json").open("x", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)

    print("Verification folder:", output)
    print("Findings:", len(findings))
    print("Verification batches:", len(tasks))
    print("No API calls made.")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    args = parser.parse_args()

    try:
        prepare(args.report)
        return 0
    except (ValueError, OSError, SyntaxError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())