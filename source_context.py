"""Read Python source without executing it."""

import ast
import hashlib
from pathlib import Path


class InputError(ValueError):
    """An input cannot be reviewed."""


def read_text_file(path):
    path = Path(path)

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"Cannot read {path}: {exc.strerror}") from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} must contain UTF-8 text.") from exc

    if not text.strip():
        raise InputError(f"{path} is empty.")

    if "\x00" in text:
        raise InputError(f"{path} contains NUL characters.")

    return text, raw


def load_source(path):
    text, raw = read_text_file(path)

    try:
        ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise InputError(
            f"Invalid Python at line {exc.lineno}: {exc.msg}"
        ) from exc

    return {
        "path": str(Path(path)),
        "text": text,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "line_count": len(text.splitlines()),
    }


def make_sections(text, max_chars=7000, overlap_lines=15):
    """Preserve fitting functions and strings; retain every source line."""
    if type(max_chars) is not int or max_chars < 100:
        raise InputError("max_chars must be an integer of at least 100.")

    if type(overlap_lines) is not int or overlap_lines < 0:
        raise InputError("overlap_lines must be a nonnegative integer.")

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise InputError(f"Invalid Python: {exc.msg}") from exc

    lines = text.splitlines()
    numbered = [
        f"{index + 1:04d}: {line}\n"
        for index, line in enumerate(lines)
    ]

    sizes = [0]
    for number, entry in enumerate(numbered, 1):
        if len(entry) > max_chars:
            raise InputError(
                f"Line {number} exceeds the section size limit."
            )
        sizes.append(sizes[-1] + len(entry))

    functions = []
    protected = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            first = min(
                [node.lineno]
                + [item.lineno for item in node.decorator_list]
            )
            bounds = (first - 1, node.end_lineno)
            functions.append(bounds)

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            bounds = (node.lineno - 1, node.end_lineno)

        else:
            continue

        lower, upper = bounds
        if sizes[upper] - sizes[lower] <= max_chars:
            protected.append(bounds)

    safe = [True] * (len(lines) + 1)

    for lower, upper in protected:
        for boundary in range(lower + 1, upper):
            safe[boundary] = False

    sections = []
    start = 0

    while start < len(lines):
        end = start

        while (
            end < len(lines)
            and sizes[end + 1] - sizes[start] <= max_chars
        ):
            end += 1

        candidate = end
        while candidate > start and not safe[candidate]:
            candidate -= 1

        if candidate == start:
            raise InputError(
                "Overlapping protected code blocks exceed "
                "the section limit."
            )

        end = candidate

        partial = any(
            lower < start < upper or lower < end < upper
            for lower, upper in functions
        )

        sections.append({
            "section": len(sections) + 1,
            "start_line": start + 1,
            "end_line": end,
            "context": "".join(numbered[start:end]),
            "partial_function": partial,
        })

        if end == len(lines):
            break

        next_start = max(start + 1, end - overlap_lines)
        while next_start < end and not safe[next_start]:
            next_start += 1

        start = next_start

    return sections