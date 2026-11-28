"""Optional JavaScript, Bash and SQL indexing through the usual CLI."""

from importlib.util import find_spec
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reqkb.graph import build_graph
from reqkb.parse import parse_repo
from reqkb.retrieve import TfIdfIndex, build_context


HAS_PARSERS = all(find_spec(name) is not None for name in (
    "tree_sitter", "tree_sitter_javascript", "tree_sitter_bash", "tree_sitter_sql",
))


class MultilangTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.req = self.root / "mixed.md"
        self.req.write_text(
            "# Mixed repository\n\n"
            "Inspect `WidgetRegistry.get`, `setup_widgets`, `refresh_widgets` "
            "and `widget_records`.\n",
            encoding="utf-8",
        )
        sources = {
            "plain.py": "def readWidget():\n    return 'unrelated'\n",
            "widget.mjs": (
                "import { readWidget } from './reader.mjs';\n"
                "export class WidgetRegistry {\n"
                "  get() { return readWidget(); }\n"
                "}\n"
            ),
            "reader.mjs": "export const readWidget = () => 1;\n",
            "bundle.min.js": "function bundled() {}\n",
            "widget.sh": (
                "## Shell comment, not a Markdown heading\n"
                "source './helpers.sh'\n"
                "setup_widgets() {\n"
                "  log_widgets\n"
                "}\n"
                "log_widgets() { echo OK; }\n"
            ),
            "widget.sql": (
                "CREATE TABLE widget_records (id INTEGER);\n"
                "CREATE FUNCTION calculate_total(i INTEGER) RETURNS INTEGER "
                "LANGUAGE SQL AS $$ SELECT i + 1; $$;\n"
                "CREATE PROCEDURE refresh_widgets() LANGUAGE SQL "
                "AS $$ SELECT calculate_total(1); $$;\n"
                "INSERT INTO widget_records VALUES (1);\n"
            ),
            "broken.sql": "CREATE TABLE /* missing declaration\n",
            "guide.md": "## Widget guide\n\nUse the widget tools.\n",
        }
        for name, content in sources.items():
            (self.repo / name).write_text(content, encoding="utf-8")

    def run_cli(self, *args, no_site=False):
        return subprocess.run(
            [sys.executable, *(["-S"] if no_site else []), "-m", "reqkb", *args],
            cwd=ROOT,
            env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
            capture_output=True, text=True,
        )

    def test_python_remains_the_default_without_dependencies(self):
        self.assertEqual(list(parse_repo(str(self.repo))), ["guide.md", "plain.py"])
        result = self.run_cli(
            "build", "--repo", str(self.repo), "--req", str(self.req),
            "--kb", str(self.root / "kb"), "--language", "javascript", "--yes",
            no_site=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requirements-treesitter.txt", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    @unittest.skipUnless(HAS_PARSERS, "install requirements-treesitter.txt")
    def test_sql_snippets_include_the_matching_statement(self):
        path = self.repo / "queries.sql"
        relevant = "SELECT id FROM orders WHERE fulfillment_status = 'queued';"
        path.write_text(
            "CREATE TABLE orders (id INTEGER, fulfillment_status TEXT);\n"
            "SELECT id FROM jobs;\n"
            "SELECT id FROM branches;\n"
            "SELECT id FROM labels;\n"
            f"{relevant}\n"
            "SELECT id FROM users;\n",
            encoding="utf-8",
        )
        files = parse_repo(str(self.repo), languages=("sql",))
        context = build_context(
            files, "query", "Find `orders` queries filtering by `fulfillment_status`."
        )
        entry = next(entry for entry in context.files if entry["path"] == path.name)
        self.assertIn(relevant, [symbol["snippet"] for symbol in entry["symbols"]])

    @unittest.skipUnless(HAS_PARSERS, "install requirements-treesitter.txt")
    def test_mixed_repository_keeps_code_symbols_and_edges(self):
        files = parse_repo(str(self.repo), languages=("javascript", "bash", "sql"))
        self.assertNotIn("bundle.min.js", files)
        self.assertEqual(files["widget.mjs"].imports, ["./reader.mjs"])
        self.assertEqual(files["widget.sh"].imports, ["./helpers.sh"])
        self.assertEqual(files["widget.sql"].symbols["widget_records"], 1)
        self.assertEqual(files["widget.sql"].snippet("statement_4_1"),
                         (4, 4, "INSERT INTO widget_records VALUES (1);"))
        self.assertTrue(files["broken.sql"].is_code)

        _, edges = build_graph(files)
        self.assertEqual(edges["widget.mjs", "WidgetRegistry.get"],
                         {("reader.mjs", "readWidget")})
        self.assertEqual(edges["widget.sh", "setup_widgets"],
                         {("widget.sh", "log_widgets")})
        self.assertEqual(edges["widget.sql", "refresh_widgets"],
                         {("widget.sql", "calculate_total")})
        self.assertEqual(
            files["widget.sh"].snippet("setup_widgets"),
            (3, 5, "setup_widgets() {\n  log_widgets\n}"),
        )
        index = TfIdfIndex(files)
        self.assertEqual(index.section_cosine(index.vector(["shell"]), "widget.sh"),
                         (0.0, None))

    @unittest.skipUnless(HAS_PARSERS, "install requirements-treesitter.txt")
    def test_sql_graph_folds_unquoted_names_and_keeps_quoted_case(self):
        (self.repo / "case.sql").write_text(
            "CREATE FUNCTION Calc(i INTEGER) RETURNS INTEGER "
            "LANGUAGE SQL AS $$ SELECT i; $$;\n"
            'CREATE FUNCTION "CaLc"(i INTEGER) RETURNS INTEGER '
            "LANGUAGE SQL AS $$ SELECT i; $$;\n"
            "SELECT CALC(1);\n"
            'SELECT "CaLc"(1);\n'
            'SELECT "CALC"(1);\n',
            encoding="utf-8",
        )
        files = parse_repo(str(self.repo), languages=("sql",))
        _, edges = build_graph(files)
        self.assertEqual(edges["case.sql", "statement_3_1"], {("case.sql", "calc")})
        self.assertEqual(edges["case.sql", "statement_4_1"], {("case.sql", "CaLc")})
        self.assertEqual(edges["case.sql", "statement_5_1"], set())

    @unittest.skipUnless(HAS_PARSERS, "install requirements-treesitter.txt")
    def test_sql_requirement_seeds_follow_identifier_case(self):
        (self.repo / "plain-schema.sql").write_text(
            "CREATE TABLE WidgetRecords (id INTEGER);\n", encoding="utf-8"
        )
        (self.repo / "quoted-schema.sql").write_text(
            'CREATE TABLE "WidgetRecords" (id INTEGER);\n', encoding="utf-8"
        )
        files = parse_repo(str(self.repo), languages=("sql",))
        for spelling, expected in (
            ("WidgetRecords", ["plain-schema.sql"]),
            ("WIDGETRECORDS", ["plain-schema.sql"]),
            ('"WidgetRecords"', ["quoted-schema.sql"]),
            ('"WIDGETRECORDS"', []),
        ):
            with self.subTest(spelling=spelling):
                ctx = build_context(files, "case", f"Find `{spelling}`.", level="vibe")
                self.assertEqual(ctx.file_paths(), expected)

    @unittest.skipUnless(HAS_PARSERS, "install requirements-treesitter.txt")
    def test_both_pipeline_entry_points_accept_optional_languages(self):
        languages = ("--language", "javascript", "--language", "bash", "--language", "sql")
        common = ("--repo", str(self.repo), "--req", str(self.req), *languages)
        kb = self.root / "kb"
        built = self.run_cli("build", *common, "--kb", str(kb), "--yes")
        self.assertEqual(built.returncode, 0, built.stderr)
        page = (kb / "requirements/mixed.md").read_text(encoding="utf-8")
        self.assertIn("`WidgetRegistry.get` (L3)", page)
        self.assertIn("`setup_widgets` (L3)", page)
        self.assertIn("`refresh_widgets` (L3)", page)
        checked = self.run_cli(
            "eval", *common, "--expected", "widget.mjs,widget.sh,widget.sql",
            "--core", "widget.sql", "--min-recall", "3",
        )
        self.assertEqual(checked.returncode, 0, checked.stderr + checked.stdout)


if __name__ == "__main__":
    unittest.main()
