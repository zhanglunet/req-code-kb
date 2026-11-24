#!/usr/bin/env python3
"""Static site generator for req-code-kb knowledge bases. Stdlib only.

Input:  one or more kb/ directories (index.json + requirements/*.md),
        listed in sources.json.
Output: dist/ — index.html plus one HTML page per requirement, with
        Mermaid call-chain diagrams rendered by a vendored mermaid.js.

Usage:
    python3 sitegen.py [--config sources.json] [--out dist]
                       [--base-url https://req-code-kb.pages.dev]

Re-running after new knowledge pages are settled picks them up
automatically; no page HTML is ever hand-written.

Safety: lines that leak local absolute paths (the "来源：/home/..."
line some pages carry) are dropped before rendering, and sources.json
itself is never copied into dist/.
"""
import argparse
import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CJK = r"\u4e00-\u9fff"
_CJK_END = re.compile("[" + CJK + "]$")
_CJK_START = re.compile("^[" + CJK + "]")


# ---------------------------------------------------------------- Markdown
def _join_lines(lines: list[str]) -> str:
    """Join wrapped lines: no space between CJK fragments, space otherwise."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif _CJK_END.search(out) or _CJK_START.match(ln):
            out += ln
        else:
            out += " " + ln
    return out


def inline(text: str) -> str:
    """Inline markup: `code`, [text](url), **bold**, *italic*."""
    parts = re.split(r"(`[^`]+`)", text)
    out: list[str] = []
    for part in parts:
        if len(part) >= 2 and part.startswith("`") and part.endswith("`"):
            out.append("<code>" + html.escape(part[1:-1]) + "</code>")
            continue
        s = html.escape(part)
        s = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: '<a href="' + html.escape(m.group(2), quote=True)
            + '">' + m.group(1) + "</a>",
            s,
        )
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", s)
        out.append(s)
    return "".join(out)


def _split_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def _is_sep(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(re.match(r"^:?-{3,}:?$", c) for c in cells)


def md_to_html(text: str) -> tuple[str, bool]:
    """Render the Markdown subset the knowledge pages use.

    Returns (html, has_mermaid). Handles headings, paragraphs, flat
    lists (incl. task lists), GFM tables, fenced code blocks (mermaid
    gets <pre class="mermaid">), hr and blockquotes.
    """
    lines = text.splitlines()
    out: list[str] = []
    has_mermaid = False
    i = 0
    n = len(lines)

    def flush_para(buf: list[str]) -> None:
        if buf:
            out.append("<p>" + inline(_join_lines(buf)) + "</p>")
            buf.clear()

    para: list[str] = []
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_para(para)
            i += 1
            continue
        if stripped.startswith("```"):
            flush_para(para)
            lang = stripped[3:].strip().lower()
            buf: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            body = html.escape("\n".join(buf))
            if lang == "mermaid":
                has_mermaid = True
                out.append('<pre class="mermaid">' + body + "</pre>")
            elif lang:
                out.append(
                    '<pre><code class="language-' + html.escape(lang) + '">'
                    + body + "</code></pre>"
                )
            else:
                out.append("<pre><code>" + body + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(para)
            level = len(m.group(1))
            out.append(f"<h{level}>" + inline(m.group(2).strip()) + f"</h{level}>")
            i += 1
            continue
        if stripped in ("---", "***", "___"):
            flush_para(para)
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < n and _is_sep(lines[i + 1]):
            flush_para(para)
            header = _split_row(stripped)
            rows: list[list[str]] = []
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            th = "".join("<th>" + inline(c) + "</th>" for c in header)
            trs = "".join(
                "<tr>" + "".join("<td>" + inline(c) + "</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append("<table><thead><tr>" + th + "</tr></thead><tbody>" + trs + "</tbody></table>")
            continue
        if stripped.startswith("> "):
            flush_para(para)
            buf = []
            while i < n and lines[i].strip().startswith("> "):
                buf.append(lines[i].strip()[2:])
                i += 1
            out.append("<blockquote><p>" + inline(_join_lines(buf)) + "</p></blockquote>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", stripped)
        om = re.match(r"^\d+\.\s+(.*)$", stripped)
        if m or om:
            flush_para(para)
            ordered = bool(om)
            items: list[str] = []
            tag = "ol" if ordered else "ul"
            while i < n:
                cur = lines[i].strip()
                mm = re.match(r"^[-*]\s+(.*)$", cur)
                oo = re.match(r"^\d+\.\s+(.*)$", cur)
                if (ordered and not oo) or (not ordered and not mm):
                    # Wrapped continuation of the current item.
                    if cur and items and not cur.startswith(("#", "```", "|", "> ")):
                        items[-1] += "\n" + cur
                        i += 1
                        continue
                    break
                items.append((oo or mm).group(1))
                i += 1
            lis = []
            for it in items:
                it = it.strip()
                task = re.match(r"^\[([ xX])\]\s*(.*)$", it, re.S)
                if task:
                    checked = " checked" if task.group(1).lower() == "x" else ""
                    lis.append(
                        '<li><input type="checkbox" disabled' + checked + "> "
                        + inline(_join_lines(task.group(2).splitlines())) + "</li>"
                    )
                else:
                    lis.append("<li>" + inline(_join_lines(it.splitlines())) + "</li>")
            out.append(f"<{tag}>" + "".join(lis) + f"</{tag}>")
            continue
        para.append(line)
        i += 1
    flush_para(para)
    return "".join(out), has_mermaid


# ------------------------------------------------------------- page parsing
LOCAL_PATH = re.compile(r"/home/|/tmp/|file://")


def sanitize(text: str) -> str:
    """Drop lines that leak local absolute paths (e.g. 来源：/home/...)."""
    return "\n".join(ln for ln in text.splitlines() if not LOCAL_PATH.search(ln))


def extract_title(md: str) -> str:
    for ln in md.splitlines():
        if ln.startswith("# "):
            return ln[2:].strip()
    return "知识页"


def extract_summary(md: str, limit: int = 110) -> str:
    """First paragraph of the ## 背景 section, as plain text."""
    lines = md.splitlines()
    start = None
    for idx, ln in enumerate(lines):
        if ln.strip() == "## 背景":
            start = idx + 1
            break
    if start is None:
        return ""
    buf: list[str] = []
    for ln in lines[start:]:
        if ln.startswith("## "):
            break
        if ln.strip():
            buf.append(ln.strip())
        elif buf:
            break
    text = _join_lines(buf)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("`", "").replace("**", "")
    return (text[:limit] + "…") if len(text) > limit else text


def count_table_rows(md: str) -> int:
    """Rows of the first GFM table (the file list)."""
    lines = md.splitlines()
    for idx, ln in enumerate(lines):
        if ln.strip().startswith("|") and idx + 1 < len(lines) and _is_sep(lines[idx + 1]):
            count = 0
            j = idx + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                count += 1
                j += 1
            return count
    return 0


# ------------------------------------------------------------------- build
def render_template(name: str, **kw: str) -> str:
    tpl = (ROOT / "templates" / name).read_text(encoding="utf-8")
    for key, val in kw.items():
        tpl = tpl.replace("{{" + key + "}}", val)
    return tpl


def build_site(config_path: Path, out_dir: Path, base_url: str) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    generated = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M CST")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "assets" / "mermaid.min.js", out_dir / "assets" / "mermaid.min.js")
    shutil.copy(ROOT / "templates" / "style.css", out_dir / "assets" / "style.css")

    mermaid_js = (
        '<script src="{{root}}assets/mermaid.min.js"></script>\n'
        "<script>mermaid.initialize({startOnLoad:true});</script>"
    )
    all_pages: list[dict] = []
    index_sections: list[str] = []
    for src in config["sources"]:
        kb_dir = Path(src["kb_dir"])
        if not kb_dir.is_absolute():
            # kb_dir is relative to the repo root (the parent of site/,
            # where this generator lives). Absolute paths still work
            # for local use.
            kb_dir = ROOT.parent / kb_dir
        index_path = kb_dir / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
        req_dir = kb_dir / "requirements"
        md_files = {p.stem: p for p in sorted(req_dir.glob("*.md"))} if req_dir.exists() else {}
        page_ids = list(index.keys()) + [s for s in md_files if s not in index]
        src_dir = out_dir / src["id"]
        src_dir.mkdir(parents=True, exist_ok=True)
        cards: list[str] = []
        total_files = 0
        for req_id in page_ids:
            md_path = md_files.get(req_id)
            if md_path is None:
                print(f"  跳过 {req_id}：index.json 有登记但找不到 md", file=sys.stderr)
                continue
            raw = sanitize(md_path.read_text(encoding="utf-8"))
            title = extract_title(raw)
            body, has_mermaid = md_to_html(raw)
            files = index.get(req_id, {}).get("files", [])
            file_count = len(files) or count_table_rows(raw)
            total_files += file_count
            shared = index.get(req_id, {}).get("shared_with", [])
            shared_links = []
            for other in shared:
                if other in page_ids:
                    # Cards live on the homepage (site root); pages live
                    # under dist/<source id>/, so the link needs the
                    # source prefix too.
                    shared_links.append(
                        f'<a href="{src["id"]}/{other}.html">{html.escape(other)}</a>'
                    )
                else:
                    shared_links.append(html.escape(other))
            url = f"{src['id']}/{req_id}.html"
            page = {
                "id": req_id, "title": title, "source": src,
                "file_count": file_count, "shared": shared,
                "shared_links": shared_links, "summary": extract_summary(raw),
                "url": url,
            }
            all_pages.append(page)
            shared_html = (
                "<p class=\"meta\">相关需求： " + "、".join(shared_links) + "</p>"
                if shared_links else ""
            )
            cards.append(
                f'<article class="card"><h3><a href="{src["id"]}/{req_id}.html">{html.escape(title)}</a></h3>'
                f"<p>{html.escape(page['summary'])}</p>"
                f'<p class="meta">{file_count} 个文件 · {len(shared)} 个共享需求</p>'
                f"{shared_html}</article>"
            )
            crumb = (
                f'<p class="crumb"><a href="../index.html">首页</a> / '
                f"<a href=\"../index.html#{src['id']}\">{html.escape(src['title'])}</a> / "
                f"{html.escape(title)}</p>"
            )
            page_html = render_template(
                "base.html",
                title=f"{title} · {src['title']}",
                root="../",
                content=crumb + body,
                generated=generated,
                mermaid=mermaid_js.replace("{{root}}", "../") if has_mermaid else "",
            )
            (src_dir / f"{req_id}.html").write_text(page_html, encoding="utf-8")
        index_sections.append(
            f'<section class="source" id="{src["id"]}">'
            f"<h2>{html.escape(src['title'])}</h2>"
            f"<p class=\"lead\">{html.escape(src.get('blurb', ''))}</p>"
            f"<p class=\"muted\">源仓库：<a href=\"{html.escape(src['repo_url'], quote=True)}\">"
            f"{html.escape(src['repo_name'])}</a> · {len(cards)} 页 · 共 {total_files} 个文件</p>"
            f"<div class=\"cards\">" + "".join(cards) + "</div></section>"
        )
    intro = (
        "<h1>需求代码知识库</h1>"
        "<p class=\"lead\">req-code-kb：req 是 requirement（需求），code 是代码，"
        "kb 是 knowledge base（知识库）。一个需求，只备它要用的料。</p>"
        "<h2>这是什么</h2>"
        "<p>按需求建代码知识库的工具和方法：不把整个仓库倒给读者或模型，"
        "而是给每个需求挑一份“最小完备上下文”——刚好够把这个需求讲清楚、改得动、验得过。"
        "工具是零依赖 Python，来源有三路：代码仓库、需求文档、群消息。</p>"
        "<h2>解决什么问题</h2>"
        "<p>仓库动辄上千个文件，想弄懂一个需求，得翻全仓找相关代码；"
        "把整仓喂给模型又贵又吵，关键文件常被噪声淹没；新人接手更不知道从哪看起。"
        "这个知识库把“找相关文件”做成可重复的流程：从需求文档里抽标识符当种子，"
        "沿调用图取直接邻居，再按 PageRank 过滤二跳邻居，token 预算 8000 截断，"
        "最后由人确认才定稿。</p>"
        "<h2>一页里有什么</h2>"
        "<p>每份知识页对应一个需求，包含需求原文、相关文件表（链接精确到 GitHub 提交）、"
        "调用链图、群消息佐证、验收清单。</p>"
        "<h2>怎么用</h2>"
        "<p>写一份需求文档 → <code>reqkb build</code> 沉淀成知识页 → "
        "重新跑一遍生成器收进本站；想提问用 <code>reqkb ask</code>，"
        "想验效果用 <code>reqkb eval</code> 跑盲测。"
        "新需求来了，重复这个流程就行，不用手写页面。</p>"
        "<h2>凭什么可信</h2>"
        "<p>方法在 pallets/click 上做过盲测：拿两个已合并的 PR 当考题，只给需求描述、"
        "仓库回到改动前，再对照真实改动文件——#3896 找回 3/5 个文件，#3878 找回 2/4，"
        "核心文件都在内。方法见<a href=\"https://github.com/zhanglunet/req-code-kb/blob/main/docs/mvp-plan.md\">"
        "盲测方法说明</a>。</p>"
        "<p>下边按来源仓库列出全部知识页。</p>"
    )
    home = render_template(
        "base.html",
        title="首页",
        root="",
        content=intro + "".join(index_sections),
        generated=generated,
        mermaid="",
    )
    (out_dir / "index.html").write_text(home, encoding="utf-8")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{base_url}/</loc></url>\n"
        + "".join(
            f"  <url><loc>{base_url}/{p['url']}</loc></url>\n" for p in all_pages
        )
        + "</urlset>\n"
    )
    (out_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (out_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    return {
        "pages": len(all_pages),
        "sources": len(config["sources"]),
        "out": str(out_dir),
        "generated": generated,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the req-code-kb static site.")
    ap.add_argument("--config", default=str(ROOT / "sources.json"))
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--base-url", default="https://req-code-kb.pages.dev")
    args = ap.parse_args()
    stats = build_site(Path(args.config), Path(args.out), args.base_url)
    print(f"生成完毕：{stats['sources']} 个来源，{stats['pages']} 页 -> {stats['out']}（{stats['generated']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
