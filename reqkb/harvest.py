"""Knowledge flywheel: compare a settled page with the real change.

The AIspec harvest step in miniature. After a PR merges, the files
it really changed are the ground truth: what the page predicted and
got right is confirmation, what it missed is the next thing to learn
from. The record is appended as a dated entry, never rewriting the
settled file list, so the original prediction stays auditable.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess

HARVEST_HEADING = "## 回流记录"

_PAGE_FILE_RE = re.compile(r"^\|\s*\[([^\]]+)\]\(", re.M)


def compare(predicted: list[str], changed: list[str]) -> dict:
    """Hits / misses / extras between prediction and reality."""
    predicted_set = set(predicted)
    changed_set = set(changed)
    hits = sorted(predicted_set & changed_set)
    misses = sorted(changed_set - predicted_set)
    extras = sorted(predicted_set - changed_set)
    return {
        "hits": hits, "misses": misses, "extras": extras,
        "recall": f"{len(hits)}/{len(changed_set)}" if changed_set else "0/0",
    }


def changed_files_from_git(repo_path: str, base: str, head: str) -> list[str]:
    """Files changed between two refs (base...head, PR-style range)."""
    out = subprocess.run(
        ["git", "-C", repo_path, "diff", "--name-only", f"{base}...{head}"],
        capture_output=True, text=True, check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _page_files(page: str) -> list[str]:
    return _PAGE_FILE_RE.findall(page)


def harvest(kb_dir: str, req_id: str, changed: list[str],
            pr_ref: str = "", date: str | None = None) -> dict:
    """Append a harvest record to the page and kb/index.json.

    Returns the comparison (hits / misses / extras / recall).
    """
    page_path = os.path.join(kb_dir, "requirements", f"{req_id}.md")
    if not os.path.exists(page_path):
        raise FileNotFoundError(f"no settled page for {req_id}: {page_path}")
    with open(page_path, encoding="utf-8") as fh:
        page = fh.read()
    index_path = os.path.join(kb_dir, "index.json")
    index: dict = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    entry = index.setdefault(req_id, {"files": [], "shared_with": []})
    predicted = entry.get("files") or _page_files(page)
    result = compare(predicted, changed)
    date = date or datetime.date.today().isoformat()
    when = f"{date}（{pr_ref}）" if pr_ref else date

    def _fmt(paths: list[str]) -> str:
        return "、".join(f"`{p}`" for p in paths) if paths else "无"

    block = [
        "",
        f"- {when}：真实改动 {len(changed)} 个文件，命中 "
        f"{len(result['hits'])} 个，召回 {result['recall']}。",
        f"  - 命中：{_fmt(result['hits'])}",
        f"  - 漏掉：{_fmt(result['misses'])}"
        + ("——下次同类需求先看这类文件。" if result["misses"] else ""),
        f"  - 多余：{_fmt(result['extras'])}",
    ]
    if HARVEST_HEADING not in page:
        page = page.rstrip("\n") + "\n\n" + HARVEST_HEADING + "\n"
    page = page.rstrip("\n") + "\n" + "\n".join(block) + "\n"
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    entry.setdefault("harvest", []).append({
        "date": date, "pr": pr_ref, "recall": result["recall"],
        "hits": result["hits"], "misses": result["misses"],
        "extras": result["extras"],
    })
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    return result
