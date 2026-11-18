"""File-scope C function definitions and their runtime complexity."""

from pathlib import PurePosixPath

from crapper.languages.treesitter import (
    binary_logic,
    complexity,
    descendants,
    end_line,
    node_text,
    parse,
    start_line,
)
from crapper.model import Function

_DECISIONS = {
    "if_statement",
    "for_statement",
    "while_statement",
    "do_statement",
    "case_statement",
    "conditional_expression",
}


def _module_namespace(path: str, project_root: str | None) -> str:
    relative = PurePosixPath(path.replace("\\", "/"))
    if project_root:
        root = PurePosixPath(project_root.replace("\\", "/"))
        if relative.is_relative_to(root):
            relative = relative.relative_to(root)
    parts = relative.with_suffix("").parts
    if "src" in parts[:-1]:
        parts = parts[parts.index("src") + 1 :]
    return ".".join(parts)


def _function_identifier(node):
    while node is not None and node.type != "identifier":
        if node.type == "parenthesized_declarator":
            node = next((child for child in node.named_children if child.type != "comment"), None)
        else:
            node = node.child_by_field_name("declarator")
    return node


def _is_file_scope(node) -> bool:
    parent = node.parent
    while parent is not None and parent.type.startswith("preproc_"):
        parent = parent.parent
    return parent is not None and parent.type == "translation_unit"


def _is_decision(node) -> bool:
    return node.type in _DECISIONS or binary_logic(node)


def _skip(node) -> bool:
    # Descend into conditional-compilation bodies, but not directive expressions.
    parent = node.parent
    return node.type == "function_definition" or (
        parent is not None
        and parent.type.startswith("preproc_")
        and parent.child_by_field_name("condition") == node
    )


def functions_in_source(
    source: str, path: str, project_root: str | None = None
) -> list[Function]:
    data, tree = parse(source, "c")
    namespace = _module_namespace(path, project_root)
    found: list[Function] = []
    for node in descendants(tree.root_node):
        if node.type != "function_definition" or not _is_file_scope(node):
            continue
        body = node.child_by_field_name("body")
        ident = _function_identifier(node)
        if body is None or ident is None:
            continue
        found.append(
            Function(
                name=node_text(data, ident),
                namespace=namespace,
                complexity=complexity(body, _is_decision, _skip),
                start_line=start_line(node),
                end_line=end_line(node),
                path=path,
                language="c",
                start_byte=node.start_byte,
                end_byte=node.end_byte,
            )
        )
    return found
