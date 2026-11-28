"""Render one requirement's knowledge page (fixed-structure Markdown).

Structure: requirement excerpt, related files/functions with
``file:line`` links, a Mermaid call-chain diagram, group-message
evidence (or an honest "none yet"), and the acceptance checklist.
"""

from __future__ import annotations

import json
import os

from .graph import Node
from .retrieve import LEVELS, Context


def github_link(repo_url: str, ref: str, path: str, line: int | None = None) -> str:
    url = f"{repo_url.rstrip('/')}/blob/{ref}/{path}"
    if line:
        url += f"#L{line}"
    return url


def render_page(ctx: Context, repo_url: str, ref: str,
                req_source: str, messages: list[dict]) -> str:
    req_text = ctx.req_text.strip()
    # The page already carries the requirement id as its title; drop a
    # duplicate top-level heading from the requirement document itself.
    first_line, _, rest = req_text.partition("\n")
    if first_line.startswith("# ") and ctx.req_id in first_line:
        req_text = rest.lstrip()
    lines = [
        f"# {ctx.req_id}",
        "",
        "## 需求原文",
        "",
        req_text,
        "",
        f"来源：{req_source}",
        "",
        "## 相关文件 / 函数",
        "",
        "| 文件 | 关联 | 命中符号 |",
        "| --- | --- | --- |",
    ]
    for entry in ctx.files:
        path = entry["path"]
        link = github_link(repo_url, ref, path)
        hop = {0: "种子", 1: "1 跳邻居", 2: "2 跳邻居"}.get(entry["hop"], "?")
        syms = ", ".join(
            f"`{s['name']}` (L{s['line']})" for s in entry["symbols"][:6]
        ) or "—"
        sec = entry.get("section")
        if sec is not None:
            # The winning h2 section made this file score: link to the
            # section start and show its title path + line range
            # (issue #12).
            link = github_link(repo_url, ref, path, line=sec["start_line"])
            syms = (f"§ {sec['title_path']} "
                    f"(L{sec['start_line']}-L{sec['end_line']})")
        lines.append(f"| [{path}]({link}) | {hop} | {syms} |")
    lines += [
        "",
        f"共 {len(ctx.files)} 个文件，约 {ctx.total_tokens} tokens（预算内）"
        f"，分级：{ctx.level}——{LEVELS[ctx.level]['label']}。",
        "",
        "## 调用链",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    edges = _mermaid_edges(ctx)
    if edges:
        lines += [f"    {a} --> {b}" for a, b in edges]
    else:
        lines.append("    %% 种子符号之间没有直接调用关系")
    lines += [
        "```",
        "",
        "## 影响面",
        "",
        "改种子文件之前先看这一节：列出调用种子符号的上游文件，"
        "也就是改动最先波及的地方（取每文件前 3 个调用者，按调用者重要性排序）。",
        "",
    ]
    if ctx.impact:
        for entry in ctx.files:
            if entry["hop"] != 0 or entry["path"] not in ctx.impact:
                continue
            callers = "、".join(
                f"`{c.rsplit(':', 1)[0]}` 的 `{c.rsplit(':', 1)[1]}`"
                for c in ctx.impact[entry["path"]]
            )
            lines.append(f"- 改 `{entry['path']}` 会波及：{callers}")
    else:
        lines.append("种子符号暂无站外调用者。")
    lines += [
        "",
        "## 群消息佐证",
        "",
    ]
    if messages:
        for msg in messages:
            lines.append(
                f"- {msg.get('time', '')} {msg.get('sender', '')}"
                f"（{msg.get('group', '')}）：{msg.get('text', '')}"
            )
    else:
        lines.append("暂无。")
    lines += [
        "",
        "## 验收",
        "",
        "- [ ] 核心改动文件在上方清单中",
        "- [ ] 召回覆盖真实改动文件（盲测见 `tests/test_blind.py`）",
        "",
    ]
    return "\n".join(lines) + "\n"


def _mermaid_edges(ctx: Context) -> list[tuple[str, str]]:
    """Seed symbol -> its 1-hop callees, as Mermaid-safe node ids."""
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in ctx.files:
        if entry["hop"] != 0:
            continue
        for sym in entry["symbols"]:
            src = _node_id(entry["path"], sym["name"])
            for _name in sym.get("callees", []):
                dst = _node_id(entry["path"], _name)
                if (src, dst) not in seen:
                    seen.add((src, dst))
                    edges.append((src, dst))
    return edges[:20]


def _node_id(path: str, qualname: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in path + "__" + qualname)


def update_index(kb_dir: str, ctx: Context) -> dict:
    """Maintain kb/index.json: requirement -> files, shared across reqs."""
    path = os.path.join(kb_dir, "index.json")
    index: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            index = json.load(fh)
    entry = index.setdefault(ctx.req_id, {"files": [], "shared_with": []})
    entry["files"] = ctx.file_paths()
    for other_id, other in index.items():
        if other_id == ctx.req_id:
            continue
        shared = sorted(set(other["files"]) & set(entry["files"]))
        if shared:
            if other_id not in entry["shared_with"]:
                entry["shared_with"].append(other_id)
            if ctx.req_id not in other.setdefault("shared_with", []):
                other["shared_with"].append(ctx.req_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
    return index
