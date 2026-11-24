"""Determinism: the same input must build the same page byte for byte.

Regression (2026-11-24, caught by the demo rehearsal): the same
`build` run twice produced the same 10 files but different symbols
inside them (7445 vs 7951 tokens). Cause: the call graph is built from
sets, so PageRank ties -- and last-bit float noise in the ranks -- were
broken by set iteration order, which changes with every process
(PYTHONHASHSEED). Every rank-based sort now rounds to 9 decimals and
ends in a name tiebreak. This test builds the same repo in two separate
processes with different hash seeds and diffs the pages.

Run:  python3 tests/test_determinism.py
Uses a tiny synthetic repo (no network, no fixtures on disk).
"""

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REPO_FILES = {
    "core.py": '''"""Core module."""

def seed_fn():
    return 1
''',
    # Eight callers of the seed, all uncalled themselves: they all tie
    # on PageRank, so the top-5 pick used to depend on set order.
    "tests/test_core.py": "\n".join(
        [
            '"""Tests for the seed."""',
            "",
            "from core import seed_fn",
            "",
        ]
        + [
            f"def test_{c}():\n    assert seed_fn() == 1\n"
            for c in "abcdefgh"
        ]
    ),
}

REQ_TEXT = """# test-determinism

给 `seed_fn` 加一个参数，让调用方能传配置。
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = os.path.join(tmp, "repo")
        # req_id comes from the filename, so name it after the test.
        req_path = os.path.join(tmp, "test-determinism.md")
        os.makedirs(os.path.join(repo_dir, "tests"))
        for name, text in REPO_FILES.items():
            with open(os.path.join(repo_dir, name), "w",
                      encoding="utf-8") as fh:
                fh.write(text)
        with open(req_path, "w", encoding="utf-8") as fh:
            fh.write(REQ_TEXT)
        pages = []
        for seed in ("0", "12345"):
            kb_dir = os.path.join(tmp, f"kb-{seed}")
            env = dict(os.environ, PYTHONHASHSEED=seed)
            proc = subprocess.run(
                [sys.executable, "-m", "reqkb", "build",
                 "--repo", repo_dir, "--req", req_path,
                 "--kb", kb_dir, "--yes"],
                cwd=ROOT, env=env, capture_output=True, text=True,
            )
            if proc.returncode != 0:
                print(f"FAIL: build with PYTHONHASHSEED={seed} failed:")
                print(proc.stdout)
                print(proc.stderr)
                return 1
            with open(os.path.join(
                    kb_dir, "requirements", "test-determinism.md"),
                    encoding="utf-8") as fh:
                pages.append(fh.read())
    if pages[0] != pages[1]:
        print("FAIL: same input built different pages across processes")
        for i, line in enumerate(pages[0].splitlines()):
            other = pages[1].splitlines()
            if i >= len(other) or other[i] != line:
                print(f"  first diff at line {i + 1}:")
                print(f"    seed 0:     {line[:160]}")
                print(f"    seed 12345: "
                      f"{other[i][:160] if i < len(other) else '<missing>'}")
                break
        return 1
    print("确定性：全部通过（不同 hash 种子构建结果逐字相同）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
