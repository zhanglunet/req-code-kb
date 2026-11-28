"""Ranking floor: a file that defines (or is named after) a seed must
make the cut even when files that merely call the seed outscore it.

Regression for a real miss on CLI-Anything (2026-11-24): in req-core,
`cli-anything-plugin/repl_skin.py` (defines `ReplSkin`) ranked 388th by
score and never entered the top 10, while its callers did; the canonical
`skill_generator.py` lost to an app copy, and `docs/PREVIEW_PROTOCOL.md`
was not a candidate at all. Three rules are pinned here:

1. filename tier: a file named after a seed goes first in the walk;
2. defines tier: a file defining a seed symbol goes next (this is the
   `ui.py` case below -- the requirement names the class, not the file);
3. one file per stem in the floor group: the shallowest copy wins
   (the plugin's own `skill_generator.py`, not an app copy that
   happens to score higher).
4. prefix tier is weak: a file whose name merely *starts with* a seed
   (`previewer.py` for `preview`) gets a small bonus only -- a file
   that *defines* a seed must still come first, even when the
   prefix file scores higher on raw TF-IDF. (Real case: hub's
   `search_members.py` starts with `search` and is just an app
   command; it must not ride into the top 10 on the name alone.)

Run:  python3 tests/test_floor.py
Uses a tiny synthetic repo (no network, no fixtures on disk).
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reqkb.parse import parse_repo  # noqa: E402
from reqkb.retrieve import (  # noqa: E402
    TfIdfIndex,
    build_context,
    extract_seed_identifiers,
    score_files,
)

REPO_FILES = {
    # Defines tier: defines ReplSkin, but the file is NOT named after
    # it, and its text shares almost no vocabulary with the requirement
    # -- so the callers below outscore it on TF-IDF + call bonuses.
    "plugin/ui.py": '''"""Shared UI widgets."""

class ReplSkin:
    """Renders the interactive prompt."""

    def draw(self):
        return "repl"

    def show(self):
        return "> "
''',
    # Filename tier: named after a seed.
    "plugin/skill_generator.py": '''"""Generate SKILL.md files from decorators."""

def generate_skill(name):
    return {"name": name}

def extract_meta(module):
    return {}
''',
    # Same name, deeper, deliberately higher-scoring (its docstring
    # repeats the seed words). The shallowest copy must still win.
    "app/agent-harness/skill_generator.py": '''"""skill_generator skill_generator skill_generator skill_generator.

Generates skill files from skill_generator metadata, skill_generator
decorators, skill_generator setup files and skill_generator READMEs.
"""

def generate_skill(name):
    return {"name": name}
''',
    # Filename tier, document: named after a seed, no symbols at all.
    "docs/PREVIEW_PROTOCOL.md": """# Preview protocol

The `preview` command writes state; the hub reads it.
Production and consumption are split: one side writes the
preview state, the other side displays it.
""",
    # Prefix tier: the name merely starts with a seed (`preview`), it
    # defines nothing the requirement names, and its docstring repeats
    # the seed words so it outscores the defining file on raw TF-IDF.
    # It must still come AFTER plugin/ui.py in the walk order.
    "plugin/previewer.py": '''"""preview preview preview preview preview preview preview.

Renders a `preview` of the `ReplSkin` prompt: the preview shows the
render result and the prompt text before the preview is written.
"""

def preview_all(state):
    return state

def preview_one(item):
    return item
''',
    # Callers: short, seed-dense, and they call three seed symbols
    # (ReplSkin, render, prompt), so they outscore the defining file.
    "tests/test_repl.py": '''"""ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin."""

from plugin.ui import ReplSkin

def test_render():
    skin = ReplSkin()
    assert skin.render() == "repl"

def test_prompt():
    skin = ReplSkin()
    assert skin.prompt() == "> "
''',
    "tests/test_skin.py": '''"""ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin ReplSkin."""

from plugin.ui import ReplSkin

def test_render_again():
    skin = ReplSkin()
    assert skin.render() == "repl"

def test_prompt_again():
    skin = ReplSkin()
    assert skin.prompt() == "> "
''',
}

REQ_TEXT = """# test-floor

把 `ReplSkin` 的渲染抽出来：一个统一的 REPL 界面类，
`skill_generator.py` 负责生成技能，预览机制见 `docs/PREVIEW_PROTOCOL.md`，
`preview` 的生产消费分工写清楚。测试里 `render`、`prompt`、`preview`
都要覆盖。
"""


def test_weak_exact_name() -> None:
    """A basename match alone must not outrank the implementation."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for path, text in {
            "vendor/install.py": "def provision():\n    return None\n",
            "hub/installer.py": "def resolve_package():\n    return 'registry package'\n",
        }.items():
            source = root / path
            source.parent.mkdir(exist_ok=True)
            source.write_text(text, encoding="utf-8")
        query = "Use `install` to `resolve_package` against the registry."
        files = parse_repo(tmp)
        context = build_context(files, "install", query)
        assert context.file_paths()[0] == "hub/installer.py", context.file_paths()
        explicit_query = query.replace("`install`", "`vendor/install.py`")
        explicit = build_context(files, "install", explicit_query)
        assert explicit.file_paths()[0] == "vendor/install.py", explicit.file_paths()


def test_explicit_file_survives_stem_dedup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "rendering.md").write_text("# Rendering output formatting\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src/rendering.py").write_text("def rendering():\n    return 1\n", encoding="utf-8")
        files = parse_repo(tmp)
        for filename in ("rendering.py", "./src/rendering.py"):
            context = build_context(files, "rendering", f"Update `{filename}` for output formatting.")
            assert "src/rendering.py" in context.file_paths(), context.file_paths()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        req_path = os.path.join(tmp, "req.md")
        repo_dir = os.path.join(tmp, "repo")
        os.makedirs(repo_dir)
        for name, text in REPO_FILES.items():
            path = os.path.join(repo_dir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        with open(req_path, "w", encoding="utf-8") as fh:
            fh.write(REQ_TEXT)
        files = parse_repo(repo_dir)
        index = TfIdfIndex(files)
        seeds = extract_seed_identifiers(REQ_TEXT)
        scores = score_files(files, index, REQ_TEXT, seeds)
        ctx = build_context(files, "test-floor", REQ_TEXT,
                            budget_tokens=1000)
    got = set(ctx.file_paths())
    print(f"floor context ({len(got)}, {ctx.total_tokens} tokens): "
          f"{sorted(got)}")
    print(f"scores: ui={scores['plugin/ui.py']:.2f} "
          f"test_repl={scores['tests/test_repl.py']:.2f} "
          f"test_skin={scores['tests/test_skin.py']:.2f} "
          f"skill(plugin)={scores['plugin/skill_generator.py']:.2f} "
          f"skill(app)={scores['app/agent-harness/skill_generator.py']:.2f} "
          f"previewer={scores['plugin/previewer.py']:.2f}")
    failures = []
    # The floor must do real work: the callers outscore the defining
    # file, so pure score order would spend the budget on them first.
    if not scores["tests/test_repl.py"] > scores["plugin/ui.py"]:
        failures.append("test setup: a caller must outscore the defining "
                        "file, or the floor proves nothing")
    if not scores["plugin/previewer.py"] > scores["plugin/ui.py"]:
        failures.append("test setup: the prefix file must outscore the "
                        "defining file on raw score, or the weak-prefix "
                        "rule proves nothing")
    if not scores["app/agent-harness/skill_generator.py"] > \
            scores["plugin/skill_generator.py"]:
        failures.append("test setup: the deeper copy must outscore the "
                        "plugin copy, or the shallowest-wins rule proves "
                        "nothing")
    if "plugin/ui.py" not in got:
        failures.append("defining file plugin/ui.py must be in")
    if "plugin/skill_generator.py" not in got:
        failures.append("stem-named plugin/skill_generator.py must be in")
    if "app/agent-harness/skill_generator.py" in got:
        failures.append("deeper copy app/agent-harness/skill_generator.py "
                        "must lose to the shallowest copy (one file per "
                        "stem)")
    if "docs/PREVIEW_PROTOCOL.md" not in got:
        failures.append("stem-named docs/PREVIEW_PROTOCOL.md must be in")
    if "plugin/previewer.py" in got and "plugin/ui.py" in got and \
            ctx.file_paths().index("plugin/ui.py") > \
            ctx.file_paths().index("plugin/previewer.py"):
        failures.append("weak prefix tier: plugin/ui.py (defines a seed) "
                        "must come before plugin/previewer.py (name "
                        "merely starts with a seed), even though the "
                        "prefix file scores higher")
    if ctx.total_tokens > 1000:
        failures.append("budget exceeded")
    if failures:
        print("FAIL:")
        for msg in failures:
            print("  - " + msg)
        return 1
    test_weak_exact_name()
    test_explicit_file_survives_stem_dedup()
    print("保底：全部通过（定义文件进前排、同名只留最浅一份）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
