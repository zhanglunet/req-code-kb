"""Command line: build a requirement's knowledge page, ask the KB,
or run the blind-test evaluation.

Usage:
    python -m reqkb build --repo <path-or-URL> --req examples/click-req-3896.md
    python -m reqkb ask --kb kb --q "CliRunner.invoke 怎么传 context 设置？"
    python -m reqkb eval --repo <pre-PR checkout> --req <req doc>
                         --expected <comma-separated real files>
                         --core <core file> --min-recall <n>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

from .parse import parse_repo
from .qa import ask
from .render import render_page, update_index
from .retrieve import build_context, extract_seed_identifiers, tokenize


def _load_req(path: str) -> tuple[str, str]:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    req_id = os.path.splitext(os.path.basename(path))[0]
    return req_id, text


def _repo_local_path(repo: str) -> tuple[str, str | None]:
    """Return (local path, temp dir to clean up or None)."""
    if os.path.isdir(repo):
        return repo, None
    tmp = tempfile.mkdtemp(prefix="reqkb-repo-")
    subprocess.run(
        ["git", "clone", "--depth", "1", repo, tmp],
        check=True, capture_output=True, text=True,
    )
    return tmp, tmp


def _git_head(path: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", path, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "main"


def _github_url(repo: str) -> str:
    if repo.startswith("http"):
        return repo[:-4] if repo.endswith(".git") else repo
    try:
        out = subprocess.run(
            ["git", "-C", repo, "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, check=True,
        )
        url = out.stdout.strip()
        if url.startswith("git@"):
            url = "https://github.com/" + url.split(":", 1)[1]
        return url[:-4] if url.endswith(".git") else url
    except Exception:
        return ""


def _load_messages(path: str | None, req_text: str) -> list[dict]:
    if not path:
        return []
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    keywords = set(tokenize(req_text)) | set(extract_seed_identifiers(req_text))
    kept = []
    for msg in raw if isinstance(raw, list) else raw.get("messages", []):
        text = msg.get("text", "")
        if keywords & set(tokenize(text)):
            kept.append(msg)
    return kept[:5]


def cmd_build(args) -> int:
    req_id, req_text = _load_req(args.req)
    repo_path, tmp = _repo_local_path(args.repo)
    try:
        files = parse_repo(repo_path)
        ctx = build_context(files, req_id, req_text, budget_tokens=args.budget)
        print(f"需求 {req_id}：种子 {ctx.seeds}")
        print(f"仓库共 {len(files)} 个文件；最小上下文 {len(ctx.files)} 个文件，"
              f"约 {ctx.total_tokens} tokens（预算 {args.budget}）")
        for entry in ctx.files:
            print(f"  [{entry['hop']}跳] {entry['path']} "
                  f"score={entry['score']} tokens={entry['tokens']}")
        if not args.yes and sys.stdin.isatty():
            answer = input("确认把这份上下文入库沉淀？[y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("已取消，未入库。")
                return 1
        repo_url = args.repo_url or _github_url(args.repo)
        ref = args.ref or _git_head(repo_path)
        messages = _load_messages(args.messages, req_text)
        page = render_page(ctx, repo_url, ref, args.req, messages)
        out_dir = os.path.join(args.kb, "requirements")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{req_id}.md")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(page)
        update_index(args.kb, ctx)
        print(f"已沉淀：{out_path}")
        return 0
    finally:
        if tmp:
            subprocess.run(["rm", "-rf", tmp], check=False)


def cmd_ask(args) -> int:
    result = ask(args.kb, args.q)
    if not result["hits"]:
        print("知识库里没有相关片段，我不知道。")
        return 0
    for hit in result["hits"]:
        print(f"[{hit['score']}] {hit['page']} §{hit['heading']}")
        print(f"    {hit['excerpt'][:200]}")
    print()
    print("---- 拼好的提示词（可直接贴给大模型）----")
    print(result["prompt"])
    return 0


def cmd_eval(args) -> int:
    req_id, req_text = _load_req(args.req)
    files = parse_repo(args.repo)
    ctx = build_context(files, req_id, req_text, budget_tokens=args.budget)
    expected = [p.strip() for p in args.expected.split(",") if p.strip()]
    got = ctx.file_paths()
    recalled = [p for p in expected if p in got]
    print(f"需求 {req_id}：输出 {len(got)} 个文件（上限 10），"
          f"约 {ctx.total_tokens} tokens")
    print(f"真实改动文件 {len(expected)} 个，命中 {len(recalled)} 个：{recalled}")
    print(f"漏掉：{[p for p in expected if p not in got]}")
    print(f"输出清单：{got}")
    ok = (args.core in got
          and len(recalled) >= args.min_recall
          and len(got) <= 10
          and ctx.total_tokens <= args.budget)
    print("验收：" + ("通过" if ok else "未通过"))
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="reqkb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="build one requirement's KB page")
    p_build.add_argument("--repo", required=True)
    p_build.add_argument("--req", required=True)
    p_build.add_argument("--kb", default="kb")
    p_build.add_argument("--budget", type=int, default=8000)
    p_build.add_argument("--messages", default=None)
    p_build.add_argument("--repo-url", default="")
    p_build.add_argument("--ref", default="")
    p_build.add_argument("--yes", action="store_true")
    p_build.set_defaults(func=cmd_build)

    p_ask = sub.add_parser("ask", help="ask the settled KB")
    p_ask.add_argument("--kb", default="kb")
    p_ask.add_argument("--q", required=True)
    p_ask.set_defaults(func=cmd_ask)

    p_eval = sub.add_parser("eval", help="blind-test one requirement")
    p_eval.add_argument("--repo", required=True)
    p_eval.add_argument("--req", required=True)
    p_eval.add_argument("--expected", required=True)
    p_eval.add_argument("--core", required=True)
    p_eval.add_argument("--min-recall", type=int, default=3)
    p_eval.add_argument("--budget", type=int, default=8000)
    p_eval.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
