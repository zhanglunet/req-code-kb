"""Section chunking for Markdown docs (issue #12).

A long doc's TF-IDF is diluted by the whole file: the section that
actually answers the requirement scores like the file's average.
Splitting a doc by h2 sections and scoring the best section fixes
the dilution at its source, and the winning section's title path +
line range is carried back as an anchor so the page points at the
exact section.

Pinned here:
1. splitting: h1 is the title-path prefix, h2 starts a section,
   h3 stays inside its section, headings inside fenced code blocks
   do not split, text before the first h2 is not a section, a file
   with no h2 has no sections;
2. scoring: the best section beats the whole-file cosine when the
   answer is section-shaped, and the winning section is the one
   about the requirement (not the first section);
3. plumbing: build_context carries the section anchor on the file
   entry when the section is what made the file score; code files
   and section-less docs get no anchor.

Run:  python3 tests/test_sections.py
Uses a tiny synthetic repo (no network, no fixtures on disk).
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reqkb.parse import parse_repo  # noqa: E402
from reqkb.retrieve import (  # noqa: E402
    TfIdfIndex,
    score_files,
    build_context,
    extract_seed_identifiers,
    split_markdown_sections,
    tokenize,
)

DOC_SPLIT = """# Guide to Widgets

Intro paragraph about widgets in general.

## Overview

General overview text.

### Sub detail

More overview text.

## Context Settings

Additional keyword arguments passed to `WidgetRunner.invoke`.

```python
## Not A Heading
x = 1
```

Tail of the section.

## Empty Tail
"""

DOC_DENSE = """# Widget Testing

Some generic intro about testing widgets and running suites.

## Basic Example

A basic example of running a widget test with the runner.
The runner invokes the command and checks the output.

## Context Settings

Additional keyword arguments passed to `WidgetRunner.invoke` will be
used to construct the initial `Context` object. For example, setting
context settings through `invoke`: pass `context_settings` with the
`color` option so the `Context` gets the right `color` value. The
`Context` object holds the `color` setting for the command, and
`invoke` forwards every keyword argument to the `Context`.
"""

DOC_NO_H2 = """# Just Notes

Some notes about widgets. `WidgetRunner.invoke` is mentioned here
and nowhere else, with no sections at all.
"""

CODE_FILE = '''"""Widget test runner."""

class WidgetRunner:
    """Runs a widget command in isolation."""

    def invoke(self, cli, args):
        return cli(args)
'''

REQ_TEXT = """# widget-req-1

给 `WidgetRunner.invoke()` 加一个 `context_settings` 参数，让测试能把
上下文相关的设置传给命令的 `Context`，从而解决 `color` 的名字冲突。
"""


def main() -> int:
    failures = []

    # 1. Splitting.
    sections = split_markdown_sections(DOC_SPLIT.splitlines())
    if [s["heading"] for s in sections] != [
            "Overview", "Context Settings", "Empty Tail"]:
        failures.append(f"split headings wrong: "
                        f"{[s['heading'] for s in sections]}")
    else:
        overview, context, empty = sections
        if overview["title_path"] != "Guide to Widgets / Overview":
            failures.append("title_path must carry the h1 prefix: "
                            f"{overview['title_path']!r}")
        if (overview["start_line"], overview["end_line"]) != (5, 12):
            failures.append("Overview lines must be 5-12: "
                            f"{overview['start_line']}-"
                            f"{overview['end_line']}")
        if (context["start_line"], context["end_line"]) != (13, 23):
            failures.append("Context Settings lines must be 13-23: "
                            f"{context['start_line']}-"
                            f"{context['end_line']}")
        if "Sub detail" not in overview["text"]:
            failures.append("h3 'Sub detail' must stay inside Overview")
        if "Not A Heading" not in context["text"]:
            failures.append("fenced code block must stay inside its "
                            "section")
        if (empty["start_line"], empty["end_line"]) != (24, 24):
            failures.append("Empty Tail lines must be 24-24: "
                            f"{empty['start_line']}-{empty['end_line']}")
    if split_markdown_sections(DOC_NO_H2.splitlines()) != []:
        failures.append("a file with no h2 must have no sections")

    # 2. Scoring + plumbing on a synthetic repo.
    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = os.path.join(tmp, "repo")
        for name, text in {
            "docs/guide.md": DOC_DENSE,
            "docs/notes.md": DOC_NO_H2,
            "src/widget.py": CODE_FILE,
        }.items():
            path = os.path.join(repo_dir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        files = parse_repo(repo_dir)
        index = TfIdfIndex(files)
        seeds = extract_seed_identifiers(REQ_TEXT)
        qv = index.vector(tokenize(REQ_TEXT))

        whole = index.cosine(qv, "docs/guide.md")
        sec_score, sec = index.section_cosine(qv, "docs/guide.md")
        print(f"guide.md: whole={whole:.3f} best-section={sec_score:.3f} "
              f"-> {sec['title_path'] if sec else None}")
        if sec is None or sec["heading"] != "Context Settings":
            failures.append("the winning section must be Context "
                            f"Settings, got {sec}")
        elif (sec["start_line"], sec["end_line"]) != (10, 17):
            failures.append("Context Settings lines must be 10-17: "
                            f"{sec['start_line']}-{sec['end_line']}")
        if not sec_score > whole:
            failures.append("best section must beat whole-file cosine "
                            f"({sec_score:.3f} vs {whole:.3f})")
        code_score, code_sec = index.section_cosine(qv, "src/widget.py")
        if (code_score, code_sec) != (0.0, None):
            failures.append("a code file must have no sections")
        plain_score, plain_sec = index.section_cosine(qv, "docs/notes.md")
        if (plain_score, plain_sec) != (0.0, None):
            failures.append("a doc with no h2 must have no sections")

        ctx = build_context(files, "widget-req-1", REQ_TEXT,
                            budget_tokens=8000)
        by_path = {e["path"]: e for e in ctx.files}
        if "docs/guide.md" not in by_path:
            failures.append("docs/guide.md must be in the context")
        else:
            got_sec = by_path["docs/guide.md"].get("section")
            if got_sec is None:
                failures.append("guide.md entry must carry its section "
                                "anchor")
            elif got_sec["heading"] != "Context Settings":
                failures.append("guide.md anchor must be Context "
                                f"Settings, got {got_sec}")
        if "section" in by_path.get("src/widget.py", {}):
            failures.append("a code file entry must not carry a section")
        if "section" in by_path.get("docs/notes.md", {}):
            failures.append("a section-less doc entry must not carry a "
                            "section")

    # The exact qualified reference is stronger than its parts quoted
    # independently, even when all of the existing token signals tie.
    with tempfile.TemporaryDirectory() as tmp:
        docs = {
            "a-split.md": "`WidgetRunner` `invoke`",
            "b-qualified.md": "`WidgetRunner.invoke`",
            "c-other.md": "`WidgetRunner.preview` `invoke`",
        }
        for name, reference in docs.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(f"# Guide\n\n## Options\n\n{reference} accepts keyword arguments.\n")
        for name, sections in {
            "d-qualified-last.md": [("Options 1", docs["a-split.md"]),
                                    ("Options 2", docs["b-qualified.md"])],
            "e-qualified-first.md": [("Options 2", docs["b-qualified.md"]),
                                     ("Options 1", docs["a-split.md"])],
        }.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                for heading, reference in sections:
                    fh.write(f"## {heading}\n\n{reference}\n\n")
        files = parse_repo(tmp)
        index = TfIdfIndex(files)
        question = "给 `WidgetRunner.invoke()` 加 `context_settings`。"
        scores = score_files(files, index, question,
                             extract_seed_identifiers(question))
        if not scores["b-qualified.md"] > scores["a-split.md"]:
            failures.append("an exact qualified API reference must outrank "
                            "independently quoted name parts")
        if not scores["b-qualified.md"] > scores["c-other.md"]:
            failures.append("a different method must not get the exact API boost")
        for name in ("d-qualified-last.md", "e-qualified-first.md"):
            if index.section_hits.get(name, {}).get("heading") != "Options 2":
                failures.append(f"{name} must anchor to the exact API section")

    if failures:
        print("FAIL:")
        for msg in failures:
            print("  - " + msg)
        return 1
    print("小节切分：全部通过（h2 切分、 fence 忽略、最密小节胜出、锚点带回）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
