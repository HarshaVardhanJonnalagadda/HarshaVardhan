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
    """Include every line, preserving original line numbers."""
    if max_chars < 100:
        raise InputError("max_chars must be at least 100.")

    if overlap_lines < 0:
        raise InputError("overlap_lines cannot be negative.")

    lines = text.splitlines()
    sections = []
    start = 0

    while start < len(lines):
        numbered = []
        size = 0
        end = start

        while end < len(lines):
            entry = f"{end + 1:04d}: {lines[end]}\n"

            if len(entry) > max_chars:
                raise InputError(
                    f"Line {end + 1} exceeds the section size limit."
                )

            if size + len(entry) > max_chars:
                break

            numbered.append(entry)
            size += len(entry)
            end += 1

        sections.append({
            "section": len(sections) + 1,
            "start_line": start + 1,
            "end_line": end,
            "context": "".join(numbered),
        })

        if end == len(lines):
            break

        start = max(start + 1, end - overlap_lines)

    return sections