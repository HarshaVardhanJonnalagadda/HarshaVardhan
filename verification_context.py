"""Retrieve related source without importing or executing the reviewed code."""

import ast
import re


def build_verification_context(
    source_text,
    report,
    include_callers=True,
    max_depth=3,
    caller_depth=1,
):
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("max_depth must be a nonnegative integer.")

    if type(caller_depth) is not int or caller_depth < 0:
        raise ValueError("caller_depth must be a nonnegative integer.")

    tree = ast.parse(source_text)
    lines = source_text.splitlines()
    functions = []
    classes = []

    def collect(node, prefix="", owner=None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                name = prefix + child.name
                classes.append({"name": name, "node": child})
                collect(child, name + ".", name)

            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "name": prefix + child.name,
                    "short_name": child.name,
                    "owner": owner,
                    "node": child,
                })
                collect(child, prefix + child.name + ".", owner)

    collect(tree)

    def own_nodes(node):
        """Visit this body without entering nested definitions."""
        yield node

        for child in ast.iter_child_nodes(node):
            if isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue

            yield from own_nodes(child)

    def calls_in(node):
        names = set()

        for child in own_nodes(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    names.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    names.add(child.func.attr)

        return names

    def loaded_names(node):
        return {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name)
            and isinstance(child.ctx, ast.Load)
        }

    def mentioned(name):
        return re.search(
            r"(?<!\w)" + re.escape(name) + r"(?!\w)",
            report,
            flags=re.IGNORECASE,
        ) is not None

    by_short = {}

    for index, function in enumerate(functions):
        by_short.setdefault(function["short_name"], set()).add(index)

    qualified = {
        index
        for index, function in enumerate(functions)
        if "." in function["name"] and mentioned(function["name"])
    }

    initial = set(qualified)

    if not initial:
        # Prefer explicitly formatted identifiers over words in prose.
        normalized_report = report.replace(r"\`", "`")
        code_spans = re.findall(r"`([^`\n]+)`", normalized_report)

        explicit_names = {
            span.strip().removesuffix("()").casefold()
            for span in code_spans
            if re.fullmatch(
                r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?:\(\))?",
                span.strip(),
            )
        }

        initial = {
            index
            for index, function in enumerate(functions)
            if function["name"].casefold() in explicit_names
            or function["short_name"].casefold() in explicit_names
        }

    if not initial:
        # Approximate fallback for reports without formatted identifiers.
        initial = {
            index
            for index, function in enumerate(functions)
            if mentioned(function["short_name"])
        }

    helpers = {}
    callers = {index: set() for index in range(len(functions))}
    ambiguous_by_function = {}

    for index, function in enumerate(functions):
        targets = set()
        ambiguous = set()

        for name in calls_in(function["node"]):
            candidates = by_short.get(name, set())
            targets.update(candidates)

            if len(candidates) > 1:
                ambiguous.add(name)

            # Construction can depend on __init__ or __new__.
            for class_info in classes:
                if class_info["name"].split(".")[-1] == name:
                    targets.update(
                        candidate
                        for candidate, item in enumerate(functions)
                        if item["owner"] == class_info["name"]
                        and item["short_name"] in ("__init__", "__new__")
                    )

        helpers[index] = targets
        ambiguous_by_function[index] = ambiguous

        for target in targets:
            callers[target].add(index)

    def related(index):
        result = set(helpers[index])
        owner = functions[index]["owner"]

        if owner:
            result.update(
                candidate
                for candidate, function in enumerate(functions)
                if function["owner"] == owner
                and function["short_name"] in ("__init__", "__new__")
            )

        return result

    # Expand helpers up to the configured dependency depth.
    selected = set(initial)
    frontier = set(initial)

    for _ in range(max_depth):
        following = set()

        for index in frontier:
            following.update(related(index))

        following.difference_update(selected)
        selected.update(following)
        frontier = following

        if not frontier:
            break

    # Follow callers separately, without expanding their helper trees.
    if include_callers:
        caller_frontier = set(initial)
        visited_callers = set(initial)

        for _ in range(caller_depth):
            following = set()

            for index in caller_frontier:
                following.update(callers[index])

            following.difference_update(visited_callers)
            selected.update(following)
            visited_callers.update(following)
            caller_frontier = following

            if not caller_frontier:
                break

    omitted = set()
    ambiguous = set()

    for index in selected:
        omitted.update(related(index) - selected)
        ambiguous.update(ambiguous_by_function[index])

    contexts = []
    seen_ranges = set()

    def add_context(name, node):
        decorators = getattr(node, "decorator_list", [])
        start = min([node.lineno] + [d.lineno for d in decorators])
        end = node.end_lineno

        if (start, end) in seen_ranges:
            return

        seen_ranges.add((start, end))
        contexts.append({
            "name": name,
            "start_line": start,
            "end_line": end,
            "context": "".join(
                f"{number:04d}: {lines[number - 1]}\n"
                for number in range(start, end + 1)
            ),
        })

    assignment_types = (ast.Assign, ast.AnnAssign, ast.AugAssign)

    owners = {
        functions[index]["owner"]
        for index in selected
        if functions[index]["owner"]
    }

    # Keep class fields/settings for retrieved methods and referenced classes.
    needed = set()

    for index in selected:
        needed.update(loaded_names(functions[index]["node"]))

    included_classes = set()
    class_nodes = []

    # Class fields can themselves reference another local class.
    while True:
        changed = False

        for class_info in classes:
            name = class_info["name"]

            if name in included_classes:
                continue

            if name not in owners and name.split(".")[-1] not in needed:
                continue

            included_classes.add(name)
            changed = True
            node = class_info["node"]

            for expression in (
                list(node.bases)
                + list(node.decorator_list)
                + [keyword.value for keyword in node.keywords]
            ):
                needed.update(loaded_names(expression))

            for child in node.body:
                if isinstance(child, assignment_types):
                    class_nodes.append((name + " class context", child))
                    needed.update(loaded_names(child))

        if not changed:
            break

    def defined_names(node):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return {
                alias.asname or (
                    alias.name.split(".")[0]
                    if isinstance(node, ast.Import)
                    else alias.name
                )
                for alias in node.names
            }

        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            return set()

        return {
            child.id
            for target in targets
            for child in ast.walk(target)
            if isinstance(child, ast.Name)
            and isinstance(child.ctx, ast.Store)
        }

    module_nodes = [
        node
        for node in tree.body
        if isinstance(
            node,
            (ast.Import, ast.ImportFrom) + assignment_types,
        )
    ]

    # Follow references between module definitions until stable.
    selected_module = set()

    while True:
        additions = {
            index
            for index, node in enumerate(module_nodes)
            if index not in selected_module
            and defined_names(node) & needed
        }

        if not additions:
            break

        selected_module.update(additions)

        for index in additions:
            needed.update(loaded_names(module_nodes[index]))

    for index in sorted(selected_module):
        add_context("module context", module_nodes[index])

    for name, node in class_nodes:
        add_context(name, node)

    for index in sorted(selected):
        add_context(functions[index]["name"], functions[index]["node"])

    limitations = [
        "Function calls are matched by name, not resolved runtime types.",
        "Dynamic calls, inheritance and external dependencies may be missed.",
        "Short names mentioned in prose may match unrelated functions.",
        "Only referenced top-level imports and assignments are included.",
        "Conditional module initialization and side effects are not resolved.",
        "Class headers, base implementations and decorator behavior "
        "are not fully supplied or resolved.",
        f"Caller traversal is bounded to {caller_depth} levels when "
        "enabled; caller helper trees are not expanded.",
        "Retrieved evidence does not by itself prove a defect.",
        "Missing dependencies must remain unresolved.",
    ]

    if not initial:
        limitations.append("No function names matched this finding.")

    if not include_callers:
        limitations.append("Caller retrieval was disabled.")

    if ambiguous:
        limitations.append(
            "Ambiguous call names: " + ", ".join(sorted(ambiguous))
        )

    if omitted:
        limitations.append(
            "Dependency depth limit or caller boundary left "
            "additional functions unretrieved: "
            + ", ".join(
                sorted(functions[index]["name"] for index in omitted)
            )
        )

    return {
        "matched_functions": [
            functions[index]["name"] for index in sorted(initial)
        ],
        "contexts": contexts,
        "limitations": limitations,
    }