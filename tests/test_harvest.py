"""Harvest: a settled page + index.json gain a dated flywheel record.

Run:  python3 tests/test_harvest.py
Uses a temp kb dir; nothing on disk is touched.
"""

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reqkb.harvest import compare, harvest  # noqa: E402

PAGE = """# test-req

## 需求原文

给 `seed_fn` 加参数。

## 相关文件 / 函数

| 文件 | 关联 | 命中符号 |
| --- | --- | --- |
| [a.py](https://example.com/a.py) | 种子 | `seed_fn` (L1) |
| [b.py](https://example.com/b.py) | 1 跳邻居 | `helper` (L1) |
| [c.py](https://example.com/c.py) | 2 跳邻居 | `deep` (L1) |

共 3 个文件，约 100 tokens（预算内）。

## 验收

- [ ] 核心改动文件在上方清单中
"""


def main() -> int:
    failures = []
    r = compare(["a.py", "b.py", "c.py"], ["a.py", "b.py", "d.py"])
    if (r["hits"], r["misses"], r["extras"], r["recall"]) != (
            ["a.py", "b.py"], ["d.py"], ["c.py"], "2/3"):
        failures.append(f"compare wrong: {r}")

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "requirements"))
        with open(os.path.join(tmp, "requirements", "test-req.md"),
                  "w", encoding="utf-8") as fh:
            fh.write(PAGE)
        with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8") as fh:
            json.dump({"test-req": {"files": ["a.py", "b.py", "c.py"],
                                    "shared_with": []}}, fh)
        result = harvest(tmp, "test-req", ["a.py", "b.py", "d.py"],
                         pr_ref="#1", date="2026-11-24")
        with open(os.path.join(tmp, "requirements", "test-req.md"),
                  encoding="utf-8") as fh:
            page = fh.read()
        with open(os.path.join(tmp, "index.json"), encoding="utf-8") as fh:
            index = json.load(fh)
        if "## 回流记录" not in page or "召回 2/3" not in page:
            failures.append("page missing the harvest record")
        if "`d.py`" not in page:
            failures.append("page missing the missed file d.py")
        if "a.py" not in page.split("## 回流记录")[0]:
            failures.append("harvest rewrote the settled content")
        rec = index["test-req"].get("harvest", [])
        if len(rec) != 1 or rec[0]["recall"] != "2/3" \
                or rec[0]["misses"] != ["d.py"]:
            failures.append(f"index harvest record wrong: {rec}")
        # A second harvest appends instead of replacing the first.
        harvest(tmp, "test-req", ["a.py"], pr_ref="#2", date="2026-11-25")
        with open(os.path.join(tmp, "requirements", "test-req.md"),
                  encoding="utf-8") as fh:
            page2 = fh.read()
        if page2.count("2026-11-24") != 1 or page2.count("2026-11-25") != 1:
            failures.append("second harvest did not append cleanly")
        if result["recall"] != "2/3":
            failures.append(f"harvest return wrong: {result}")
    if failures:
        print("FAIL:")
        for msg in failures:
            print("  - " + msg)
        return 1
    print("回流：全部通过（记录追加、不改沉淀、index 同步）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
