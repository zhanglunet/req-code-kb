"""Command line: build a requirement's knowledge page, ask the KB,
or run the blind-test evaluation.

Usage:
    python -m reqkb build --repo <path-or-URL> --req examples/click-req-3896.md
    python -m reqkb ask --kb kb --q "CliRunner.invoke 怎么传 context 设置？"
    python -m reqkb eval --repo <pre-PR checkout> --req <req doc>
                         --expected <comma-separated real files>
                         --core <core file> --min-recall <n>
    python -m reqkb harvest --kb kb --req click-req-3896
                            --changed-files src/click/testing.py,... --pr "#3896"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

from .harvest import changed_files_from_git, harvest
from .parse import parse_repo
from .qa import ask
from .render import render_page, update_index
from .retrieve import LEVELS, build_context, extract_seed_identifiers, tokenize
from .treesitter import EXTENSIONS, OptionalLanguageError


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
        budget = args.budget if args.budget is not None else LEVELS[args.level]["budget"]
        files = parse_repo(repo_path, languages=args.language)
        ctx = build_context(files, req_id, req_text,
                            budget_tokens=budget, level=args.level)
        print(f"需求 {req_id}：种子 {ctx.seeds}，分级 {args.level}")
        print(f"仓库共 {len(files)} 个文件；最小上下文 {len(ctx.files)} 个文件，"
              f"约 {ctx.total_tokens} tokens（预算 {budget}）")
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
    budget = args.budget if args.budget is not None else LEVELS[args.level]["budget"]
    files = parse_repo(args.repo, languages=args.language)
    ctx = build_context(files, req_id, req_text,
                        budget_tokens=budget, level=args.level)
    expected = [p.strip() for p in args.expected.split(",") if p.strip()]
    got = ctx.file_paths()
    recalled = [p for p in expected if p in got]
    print(f"需求 {req_id}：输出 {len(got)} 个文件（上限 10），"
          f"约 {ctx.total_tokens} tokens，分级 {args.level}")
    print(f"真实改动文件 {len(expected)} 个，命中 {len(recalled)} 个：{recalled}")
    print(f"漏掉：{[p for p in expected if p not in got]}")
    print(f"输出清单：{got}")
    ok = (args.core in got
          and len(recalled) >= args.min_recall
          and len(got) <= 10
          and ctx.total_tokens <= budget)
    print("验收：" + ("通过" if ok else "未通过"))
    return 0 if ok else 1


def cmd_harvest(args) -> int:
    if args.repo and args.base and args.head:
        changed = changed_files_from_git(args.repo, args.base, args.head)
    elif args.changed_files:
        changed = [p.strip() for p in args.changed_files.split(",") if p.strip()]
    else:
        print("harvest 需要 --changed-files，或 --repo + --base + --head。")
        return 1
    if not changed:
        print("没有改动文件，什么都没记。")
        return 1
    result = harvest(args.kb, args.req, changed, pr_ref=args.pr)
    print(f"需求 {args.req}：真实改动 {len(changed)} 个文件，"
          f"命中 {len(result['hits'])} 个，召回 {result['recall']}")
    print(f"命中：{result['hits']}")
    print(f"漏掉：{result['misses']}")
    print(f"多余：{result['extras']}")
    print(f"已记入 kb/requirements/{args.req}.md 的“回流记录”。")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="reqkb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="build one requirement's KB page")
    p_build.add_argument("--repo", required=True)
    p_build.add_argument("--req", required=True)
    p_build.add_argument("--kb", default="kb")
    p_build.add_argument("--level", choices=["full", "lite", "vibe"],
                         default="full",
                         help="full=2跳完整上下文，lite=1跳，vibe=只给种子文件")
    p_build.add_argument("--budget", type=int, default=None,
                         help="显式覆盖分级的 token 预算")
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
    p_eval.add_argument("--level", choices=["full", "lite", "vibe"],
                        default="full")
    p_eval.add_argument("--budget", type=int, default=None)
    p_eval.set_defaults(func=cmd_eval)

    for command in (p_build, p_eval):
        command.add_argument("--language", action="append", choices=EXTENSIONS, default=[],
                             help="启用一种可选代码语言，可重复传入")

    p_harvest = sub.add_parser(
        "harvest",
        help="record what a merged PR really changed (knowledge flywheel)")
    p_harvest.add_argument("--kb", default="kb")
    p_harvest.add_argument("--req", required=True)
    p_harvest.add_argument("--changed-files", default="",
                           help="comma-separated real changed files")
    p_harvest.add_argument("--repo", default="",
                           help="local repo path (with --base/--head, "
                                "diffs the range instead)")
    p_harvest.add_argument("--base", default="")
    p_harvest.add_argument("--head", default="")
    p_harvest.add_argument("--pr", default="", help="e.g. #3896")
    p_harvest.set_defaults(func=cmd_harvest)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OptionalLanguageError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
