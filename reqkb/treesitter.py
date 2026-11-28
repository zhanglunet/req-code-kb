"""Extract symbols and source ranges from optional Tree-sitter grammars."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import import_module


EXTENSIONS = {
    "javascript": (".js", ".mjs", ".cjs"),
    "bash": (".sh", ".bash"),
    "sql": (".sql",),
}
MODULE = "<module>"


class OptionalLanguageError(RuntimeError):
    """The requested Tree-sitter parser could not be loaded."""


@lru_cache(maxsize=len(EXTENSIONS))
def load_language(name: str):
    if name not in EXTENSIONS:
        raise ValueError(f"Unknown optional language: {name}")
    try:
        from tree_sitter import Language

        grammar = import_module(f"tree_sitter_{name}")
        return Language(grammar.language())
    except (ImportError, ValueError) as exc:
        raise OptionalLanguageError(
            f"Could not load the {name} parser. "
            "Install the optional parsers with "
            "'python -m pip install -r requirements-treesitter.txt'."
        ) from exc


@dataclass
class ParsedCode:
    ranges: dict[str, tuple[int, int]] = field(default_factory=dict)
    calls: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    imports: list[str] = field(default_factory=list)


def _text(node, source: bytes) -> str:
    if node is None:
        return ""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _lines(node) -> tuple[int, int]:
    start = node.start_point.row + 1
    end = node.end_point.row + int(node.end_point.column > 0)
    return start, max(start, end)


_JS_DEFINITIONS = {
    "class_declaration", "function_declaration", "generator_function_declaration",
    "method_definition",
}
_JS_FUNCTION_VALUES = {"arrow_function", "function_expression", "generator_function", "class"}


def _js_definition(node, source: bytes) -> str:
    if node.type == "variable_declarator":
        value = node.child_by_field_name("value")
        name = node.child_by_field_name("name")
        if value and value.type in _JS_FUNCTION_VALUES and name and name.type == "identifier":
            return _text(name, source)
    if node.type in _JS_DEFINITIONS:
        return _text(node.child_by_field_name("name"), source)
    return ""


def _js_action(node, source: bytes) -> tuple[str, str]:
    if node.type in {"import_statement", "export_statement"}:
        return "", _text(node.child_by_field_name("source"), source)[1:-1]
    field = {"call_expression": "function", "new_expression": "constructor"}.get(node.type)
    if field is None:
        return "", ""
    target = node.child_by_field_name(field)
    if target and target.type == "member_expression":
        target = target.child_by_field_name("property")
    if target is None or target.type not in {"identifier", "property_identifier", "import"}:
        return "", ""
    name = _text(target, source)
    if name in {"require", "import"}:
        arguments = node.child_by_field_name("arguments")
        argument = arguments.named_child(0) if arguments else None
        if argument and argument.type == "string":
            return "", _text(argument, source)[1:-1]
    return name, ""


def _bash_definition(node, source: bytes) -> str:
    if node.type == "function_definition":
        return _text(node.child_by_field_name("name"), source)
    return ""


def _bash_word(node, source: bytes) -> str:
    if node is None:
        return ""
    if node.type == "word":
        return _text(node, source)
    if node.type == "raw_string" or (
        node.type == "string"
        and all(child.type == "string_content" for child in node.named_children)
    ):
        return _text(node, source)[1:-1]
    return ""


def _bash_action(node, source: bytes) -> tuple[str, str]:
    if node.type != "command":
        return "", ""
    command = node.child_by_field_name("name")
    name = _bash_word(command.named_child(0) if command else None, source)
    if name in {"source", "."}:
        return "", _bash_word(node.child_by_field_name("argument"), source)
    return name, ""


_SQL_DEFINITIONS = {"create_table", "create_view", "create_materialized_view",
                    "create_function", "create_procedure"}


def _sql_identifier(node, source: bytes) -> str:
    text = _text(node, source)
    if len(text) > 1:
        closing = {'"': '"', "`": "`", "[": "]"}.get(text[0])
        if closing is not None and text[-1] == closing:
            return text[1:-1].replace(closing * 2, closing)
    return text.lower()


def _sql_object(node, source: bytes) -> str:
    return ".".join(
        _sql_identifier(child, source)
        for field in ("schema", "name")
        if (child := node.child_by_field_name(field)) is not None
    )


def _sql_definition(node, source: bytes) -> str:
    if node.type != "statement" or node.parent.type != "program":
        return ""
    for statement in node.named_children:
        if statement.type in _SQL_DEFINITIONS:
            for child in statement.named_children:
                if child.type == "object_reference":
                    return _sql_object(child, source)
    point = node.start_point
    return f"statement_{point.row + 1}_{point.column + 1}"


def _sql_action(node, source: bytes) -> tuple[str, str]:
    if node.type == "invocation":
        target = node.named_child(0)
        if target and target.type == "object_reference":
            return _sql_object(target, source).rsplit(".", 1)[-1], ""
    return "", ""


_VISITORS = {
    "javascript": (_js_definition, _js_action),
    "bash": (_bash_definition, _bash_action),
    "sql": (_sql_definition, _sql_action),
}


def parse_code(text: str, language: str) -> ParsedCode:
    """Walk recovered syntax nodes without executing or sourcing any file."""
    grammar = load_language(language)
    from tree_sitter import Parser

    source = text.encode("utf-8")
    root = Parser(grammar).parse(source).root_node
    definition, action = _VISITORS[language]
    result = ParsedCode()
    work = [(root, MODULE)]
    while work:
        node, scope = work.pop()
        if name := definition(node, source):
            scope = name if scope == MODULE else f"{scope}.{name}"
            result.ranges[scope] = _lines(node)
        callee, imported = action(node, source)
        if callee:
            result.calls.setdefault(scope, []).append((callee, node.start_point.row + 1))
        if imported:
            result.imports.append(imported)
        work.extend((child, scope) for child in reversed(node.named_children))

    if root.named_child_count and (not result.ranges or MODULE in result.calls):
        result.ranges[MODULE] = _lines(root)
    return result
