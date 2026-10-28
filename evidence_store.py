"""Save review evidence in a unique directory for each run."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


def save_text(folder, filename, text):
    """Create a new evidence file; refuse to overwrite an existing file."""
    path = Path(folder) / filename

    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)

    return path


def save_json(folder, filename, data):
    text = json.dumps(data, indent=2, ensure_ascii=False)
    return save_text(folder, filename, text + "\n")


def create_run(output_dir, source, request, rules, model):
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}_{uuid.uuid4().hex}"
    folder = root / run_id
    folder.mkdir(exist_ok=False)

    save_text(folder, "request.txt", request)
    save_text(folder, "source_snapshot.py", source["text"])
    save_text(folder, "rules.txt", rules or "No business rules supplied.")

    save_json(folder, "run_info.json", {
        "provider": "Groq",
        "model": model,
        "source_path": source["path"],
        "source_sha256": source["sha256"],
        "source_line_count": source["line_count"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    })

    save_text(
        folder,
        "validation.md",
        "# Human validation\n\n"
        "Status: pending\n\n"
        "## Supported findings\n"
        "Check each finding against the source and business rules.\n\n"
        "## Assumptions or unsupported claims\n"
        "Record missing evidence and uncertain conclusions.\n\n"
        "## Missed issues\n"
        "Record relevant issues the model did not identify.\n\n"
        "## Next checks\n"
        "Describe additional checks and whether they were performed.\n",
    )

    return folder


def save_call_input(folder, call_name, payload, context):
    """Save exactly the payload that will be passed to the API client."""
    save_json(folder, f"{call_name}_prompt.json", payload)
    save_text(folder, f"{call_name}_context.txt", context)


def save_call_success(folder, call_name, result):
    save_text(
        folder,
        f"{call_name}_raw_response.json",
        result["raw_response"],
    )
    save_text(folder, f"{call_name}_response.md", result["text"])

    save_json(folder, f"{call_name}_metadata.json", {
        "outcome": "response_complete",
        "duration_seconds": result["duration_seconds"],
        "usage": result["usage"],
    })


def save_call_failure(folder, call_name, error):
    raw = getattr(error, "raw_response", None)
    usage = {
        "input_tokens": "unknown",
        "output_tokens": "unknown",
        "total_tokens": "unknown",
    }

    if raw is not None:
        save_text(folder, f"{call_name}_raw_response.json", raw)

        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            data = None

        reported = data.get("usage") if isinstance(data, dict) else None

        if isinstance(reported, dict):
            mapping = {
                "input_tokens": "prompt_tokens",
                "output_tokens": "completion_tokens",
                "total_tokens": "total_tokens",
            }

            for destination, source in mapping.items():
                value = reported.get(source)
                if type(value) is int and value >= 0:
                    usage[destination] = value

    save_json(folder, f"{call_name}_metadata.json", {
        "outcome": "failed",
        "error": str(error),
        "duration_seconds": getattr(error, "duration_seconds", None),
        "usage": usage,
    })


def total_usage(results):
    """Unknown usage stays unknown rather than being counted as zero."""
    totals = {}

    for name in ("input_tokens", "output_tokens", "total_tokens"):
        values = [result["usage"].get(name, "unknown") for result in results]

        if values and all(type(value) is int for value in values):
            totals[name] = sum(values)
        else:
            totals[name] = "unknown"

    return totals