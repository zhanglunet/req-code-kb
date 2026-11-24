"""Levels: vibe gives seeds only, lite adds 1-hop, full adds 2-hop.

Run:  python3 tests/test_levels.py
Uses a tiny synthetic repo (no network, no fixtures on disk).
"""

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reqkb.parse import parse_repo  # noqa: E402
from reqkb.retrieve import build_context  # noqa: E402

REPO_FILES = {
    "a.py": '''"""Entry point."""

def seed_fn():
    return helper()
''',
    "b.py": '''"""Middle layer."""

def helper():
    return deep()
''',
    "c.py": '''"""Leaf layer."""

def deep():
    return 42
''',
    "d.py": '''"""Unrelated module."""

def unrelated():
    return 0
''',
    "e.py": '''"""Outside caller."""

from a import seed_fn

def uses_seed():
    return seed_fn()
''',
}

REQ_TEXT = """# test-levels

给 `seed_fn` 加一个参数，让调用方能传配置。
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        # The requirement doc lives outside the repo, as in real use
        # (otherwise the doc itself scores as a repo file).
        req_path = os.path.join(tmp, "req.md")
        repo_dir = os.path.join(tmp, "repo")
        os.makedirs(repo_dir)
        for name, text in REPO_FILES.items():
            with open(os.path.join(repo_dir, name), "w", encoding="utf-8") as fh:
                fh.write(text)
        with open(req_path, "w", encoding="utf-8") as fh:
            fh.write(REQ_TEXT)
        files = parse_repo(repo_dir)
        vibe = build_context(files, "test-levels", REQ_TEXT, level="vibe")
        lite = build_context(files, "test-levels", REQ_TEXT, level="lite")
        full = build_context(files, "test-levels", REQ_TEXT, level="full")
    v, l, f = (set(c.file_paths()) for c in (vibe, lite, full))
    print(f"vibe ({len(v)}): {sorted(v)}")
    print(f"lite ({len(l)}): {sorted(l)}")
    print(f"full ({len(f)}): {sorted(f)}")
    failures = []
    if v != {"a.py"}:
        failures.append(f"vibe should be seeds only, got {sorted(v)}")
    if "c.py" in l:
        failures.append("lite must not include the 2-hop file c.py")
    if "c.py" not in f:
        failures.append("full must include the 2-hop file c.py")
    if not (v <= l <= f):
        failures.append("levels must nest: vibe ⊆ lite ⊆ full")
    if "d.py" in f:
        failures.append("unrelated d.py must not enter any level")
    if vibe.total_tokens > 2000 or lite.total_tokens > 4000 \
            or full.total_tokens > 8000:
        failures.append("a level exceeded its token budget")
    if failures:
        print("FAIL:")
        for msg in failures:
            print("  - " + msg)
        return 1
    print("分级：全部通过（vibe ⊆ lite ⊆ full，预算各守各的）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
