"""Blind-test requirement retrieval against three already-merged Click PRs.

Method (honest version): the input is only the requirement document
(title + problem statement, changed files hidden); the repo under
test is the checkout at the PR's merge base, i.e. the code *before*
the change existed. A pass means the minimal context recalls the
files the real PR actually changed.

Reproduce:
    git clone https://github.com/pallets/click.git /tmp/click
    for case in 3896:dd149eb3 3878:2247b35e 3902:8abb77a8; do
        dest="/tmp/click-pre${case%:*}"
        mkdir "$dest"
        git -C /tmp/click archive "${case#*:}" | tar -xf - -C "$dest"
    done
    CLICK_PRE3896=/tmp/click-pre3896 CLICK_PRE3878=/tmp/click-pre3878 \
    CLICK_PRE3902=/tmp/click-pre3902 \
        python3 tests/test_blind.py

Without those checkouts the test skips (exit 0) instead of failing.
"""

import os
import subprocess
import sys

CASES = [
    {
        "req": "examples/click-req-3896.md",
        "repo_env": "CLICK_PRE3896",
        "expected": "src/click/testing.py,tests/test_testing.py,"
                    "tests/test_termui.py,docs/testing.md,CHANGES.md",
        "core": "src/click/testing.py",
        "min_recall": 4,
    },
    {
        "req": "examples/click-req-3878.md",
        "repo_env": "CLICK_PRE3878",
        "expected": "src/click/testing.py,tests/test_testing.py,"
                    "docs/testing.md,CHANGES.md",
        "core": "src/click/testing.py",
        "min_recall": 2,
    },
    {
        "req": "examples/click-req-3902.md",
        "repo_env": "CLICK_PRE3902",
        "expected": "CHANGES.md,docs/documentation.md,src/click/_textwrap.py,"
                    "src/click/formatting.py,tests/test_compat.py,tests/test_formatting.py",
        "core": "src/click/formatting.py",
        "min_recall": 3,
    },
]


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    failed = False
    ran = 0
    for case in CASES:
        repo = os.environ.get(case["repo_env"], "")
        if not repo or not os.path.isdir(repo):
            print(f"SKIP {case['req']}: set {case['repo_env']} to a "
                  f"pre-PR click checkout to run this case.")
            continue
        ran += 1
        cmd = [
            sys.executable, "-m", "reqkb", "eval",
            "--repo", repo,
            "--req", os.path.join(root, case["req"]),
            "--expected", case["expected"],
            "--core", case["core"],
            "--min-recall", str(case["min_recall"]),
        ]
        print(f"\n=== {case['req']} on {repo} ===", flush=True)
        result = subprocess.run(cmd, cwd=root)
        if result.returncode != 0:
            failed = True
    print(f"\n盲测：跑了 {ran} 个用例，"
          + ("全部通过" if not failed else "有未通过的用例"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
