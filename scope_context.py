"""Describe enclosing function structure without executing source."""

import ast


def describe_scopes(text, start_line, end_line, max_chars=3000):
    tree = ast.parse(text)
    scopes = []

    def collect(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                collect(child, prefix + child.name + ".")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append((prefix + child.name, child))
                collect(child, prefix + child.name + ".")
            else:
                collect(child, prefix)

    def walk_body(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            yield child
            yield from walk_body(child)

    collect(tree)
    entries = []

    for name, function in scopes:
        first = min(
            [function.lineno]
            + [item.lineno for item in function.decorator_list]
        )
        last = function.end_lineno

        if last < start_line or first > end_line:
            continue
        if start_line <= first and last <= end_line:
            continue

        facts = [f"FUNCTION {name}: original lines {first}-{last}."]

        for node in walk_body(function):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                facts.append(
                    f"Assignment target {node.id}: line {node.lineno}."
                )
            elif isinstance(node, ast.ExceptHandler):
                kind = ast.unparse(node.type) if node.type else "bare except"
                facts.append(
                    f"Exception handler {kind}: "
                    f"lines {node.lineno}-{node.end_lineno}."
                )
            elif isinstance(node, (ast.Try, ast.TryStar)):
                facts.append(
                    f"Try statement: lines {node.lineno}-{node.end_lineno}."
                )
                if node.finalbody:
                    facts.append(
                        "Finally body: lines "
                        f"{node.finalbody[0].lineno}-"
                        f"{node.finalbody[-1].end_lineno}."
                    )

        entries.extend(dict.fromkeys(facts))

    if not entries:
        return ""

    result = (
        "AST structural map only. Assignment locations do not prove "
        "initialization on every path. Handler locations do not prove "
        "that an operation is covered. Inspect referenced source before "
        "confirming or refuting a defect.\n"
    )
    suffix = "\nAdditional structural facts omitted due to the size limit."

    if max_chars < len(result) + len(suffix):
        raise ValueError("max_chars is too small for the structural map.")

    for entry in entries:
        if len(result) + len(entry) + 1 + len(suffix) > max_chars:
            return result + suffix
        result += entry + "\n"

    return result