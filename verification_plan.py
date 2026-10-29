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
    """Extract severity-table rows from consolidated or section reports."""
    findings = []
    seen = set()
    in_findings = False
    severities = {
        "critical", "high", "medium", "low",
        "info", "informational",
    }

    for original_line in report.splitlines():
        normalized = re.sub(r"\\([*#|`])", r"\1", original_line)
        heading = normalized.replace("*", "").strip()
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", heading)

        if match:
            title = match.group(2).strip().rstrip("#").strip().casefold()
            in_findings = title in {"findings", "important findings"}
            continue

        if not in_findings:
            continue

        row = normalized.strip()
        if not row.startswith("|"):
            continue

        cells = [
            cell.strip()
            for cell in row.strip("|").split("|")
        ]
        if len(cells) < 3:
            continue

        severity = cells[0].replace("*", "").strip().casefold()
        if severity not in severities:
            continue

        claim = original_line.strip()
        if claim not in seen:
            seen.add(claim)
            findings.append(claim)

    if not findings:
        raise ValueError(
            "No severity-table findings found under Findings or "
            "Important findings. Prose-only findings require inspection."
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
    for index, finding in enumerate(findings, 1):
        retrieved = build_verification_context(
            source["text"],
            finding,
            include_callers=True,
            max_depth=1,
            caller_depth=2,
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

        planning_blocked = None

        try:
            batches = source_batches(contexts)
        except ValueError as exc:
            planning_blocked = str(exc)
            limitations.append(
                "Verification blocked: retrieved evidence exceeds "
                "the planning size limit. No source was split or "
                "truncated, and no model assessment may be made."
            )
            batches = [
                "Evidence omitted from this blocked request. "
                "The finding remains unresolved. Original source "
                "is preserved in source_snapshot.py."
            ]

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
                "planning_blocked": planning_blocked,
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
        "extraction_limitations": [
            "Only severity-table rows under Findings or Important "
            "findings are extracted.",
            "Prose-only findings and uncertainty sections are excluded.",
            "Each extracted row is assessed as written; accompanying "
            "prose is not included.",
        ],
    }

    with (output / "plan.json").open("x", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)

    print("Verification folder:", output)
    print("Findings:", len(findings))
    print("Verification batches:", len(tasks))
    print("Scope: extracted severity-table rows only.")
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