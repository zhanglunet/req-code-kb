"""Parse a Python repo into symbols, calls and imports.

Zero-dependency: only the standard library ``ast`` module.
This is the "extract symbols" step of the Aider repo-map idea
(extract -> build graph -> PageRank -> cut by budget), reimplemented
here instead of copying ``aider/repomap.py`` so the MVP stays
dependency-free and small.
"""

from __future__ import annotations

import ast
import os

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".tox", "build", "dist", ".eggs", "egg-info",
}
MAX_MD_BYTES = 200_000


def iter_source_files(root: str):
    """Yield (relative path, absolute path) for .py and .md files."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith((".py", ".md")):
                full = os.path.join(dirpath, name)
                if name.endswith(".md") and os.path.getsize(full) > MAX_MD_BYTES:
                    continue
                out.append((os.path.relpath(full, root), full))
    return sorted(out)


def _qualname_stack(node: ast.AST) -> list[str]:
    return getattr(node, "_reqkb_stack", [])


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: dict[str, int] = {}   # qualified name -> line number
        self.calls: dict[str, list[tuple[str, int]]] = {}
        self.imports: list[str] = []
        self._stack: list[str] = []

    def _current(self) -> str:
        return ".".join(self._stack) if self._stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols[".".join(self._stack + [node.name])] = node.lineno
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._def(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._def(node)

    def _def(self, node) -> None:
        self.symbols[".".join(self._stack + [node.name])] = node.lineno
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.append(node.module.split(".")[0])
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name:
            self.calls.setdefault(self._current(), []).append((name, node.lineno))
        self.generic_visit(node)


class FileInfo:
    """One indexed file: its symbols, its calls, its raw text."""

    def __init__(self, rel_path: str, text: str) -> None:
        self.path = rel_path
        self.text = text
        self.lines = text.splitlines()
        self.symbols: dict[str, int] = {}
        self.calls: dict[str, list[tuple[str, int]]] = {}
        self.imports: list[str] = []
        self.is_code = rel_path.endswith(".py")

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.text) // 4)

    def snippet(self, qualname: str, max_lines: int = 60) -> tuple[int, int, str]:
        """Source segment of one symbol: (start line, end line, text).

        Long bodies are truncated to ``max_lines`` with an explicit
        marker: a context fragment shows the shape of a symbol, not
        the whole file. Without the cap, one big class alone (e.g.
        ``CliRunner``) eats a quarter of the token budget.
        """
        try:
            tree = ast.parse(self.text)
        except SyntaxError:
            return 1, 1, ""
        target = qualname.split(".")
        node = self._find(tree.body, target)
        if node is None:
            return 1, 1, ""
        start = node.lineno
        end = getattr(node, "end_lineno", start) or start
        if end - start + 1 > max_lines:
            text = "\n".join(self.lines[start - 1:start + max_lines - 1])
            text += "\n# ... (truncated to 60 lines)"
            return start, start + max_lines - 1, text
        return start, end, "\n".join(self.lines[start - 1:end])

    @staticmethod
    def _find(body, target):
        if not target:
            return None
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and node.name == target[0]:
                if len(target) == 1:
                    return node
                return FileInfo._find(node.body, target[1:])
        return None


def parse_file(rel_path: str, full_path: str) -> FileInfo:
    with open(full_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    info = FileInfo(rel_path, text)
    if not info.is_code:
        return info
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return info
    visitor = _Visitor()
    visitor.visit(tree)
    info.symbols = visitor.symbols
    info.calls = visitor.calls
    info.imports = visitor.imports
    return info


def parse_repo(root: str) -> dict[str, FileInfo]:
    """Parse every .py / .md file under root. Returns {rel path: FileInfo}."""
    files: dict[str, FileInfo] = {}
    for rel, full in iter_source_files(root):
        files[rel] = parse_file(rel, full)
    return files
