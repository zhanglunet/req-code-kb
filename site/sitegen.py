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


def _anchor(text: str) -> str:
    """Slug for a heading id: keep word chars + CJK, collapse the rest."""
    plain = re.sub(r"[`*_]", "", text)
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", plain).strip("-")
    return slug or "section"


_REL_BADGE = {
    "种子": '<span class="rel-badge rel-seed">种子</span>',
    "1 跳邻居": '<span class="rel-badge rel-hop1">1 跳邻居</span>',
    "2 跳邻居": '<span class="rel-badge rel-hop2">2 跳邻居</span>',
}


def _render_cell(cell: str) -> str:
    badge = _REL_BADGE.get(cell.strip())
    return badge if badge is not None else inline(cell)


def md_to_html(
    text: str, *, strip_first_h1: bool = False
) -> tuple[str, bool, list[tuple[int, str, str]]]:
    """Render the Markdown subset the knowledge pages use.

    Returns (html, has_mermaid, headings). Headings are (level, text,
    anchor); h2/h3 get id attributes so a per-page table of contents
    can link into them. Handles headings, paragraphs, flat lists
    (incl. task lists), GFM tables, fenced code blocks (mermaid gets
    a .mermaid-card wrapper), hr and blockquotes.
    """
    lines = text.splitlines()
    out: list[str] = []
    headings: list[tuple[int, str, str]] = []
    seen_anchors: dict[str, int] = {}
    has_mermaid = False
    skipped_h1 = False
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
                out.append(
                    '<div class="mermaid-card">'
                    '<div class="mermaid-bar">'
                    '<span>调用链图 · Mermaid 本地渲染</span>'
                    '<button type="button" class="mermaid-expand" aria-expanded="false">宽屏展开</button>'
                    '</div>'
                    '<pre class="mermaid">' + body + "</pre></div>"
                )
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
            text = m.group(2).strip()
            if strip_first_h1 and level == 1 and not skipped_h1:
                skipped_h1 = True
                i += 1
                continue
            anchor = _anchor(text)
            seen_anchors[anchor] = seen_anchors.get(anchor, 0) + 1
            if seen_anchors[anchor] > 1:
                anchor = f"{anchor}-{seen_anchors[anchor]}"
            headings.append((level, text, anchor))
            out.append(f'<h{level} id="{anchor}">' + inline(text) + f"</h{level}>")
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
                "<tr>" + "".join("<td>" + _render_cell(c) + "</td>" for c in r) + "</tr>"
                for r in rows
            )
            out.append(
                '<div class="table-wrap"><table><thead><tr>' + th
                + "</tr></thead><tbody>" + trs + "</tbody></table></div>"
            )
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
    return "".join(out), has_mermaid, headings


def toc_html(headings: list[tuple[int, str, str]]) -> str:
    """Per-page table of contents: sticky sidebar links to the h2 sections."""
    items = [(t, a) for lvl, t, a in headings if lvl == 2]
    if not items:
        return ""
    links = "".join(
        f'<a href="#{a}">{html.escape(t)}</a>' for t, a in items
    )
    return (
        '<aside class="doc-aside">'
        '<nav class="toc" aria-label="本页目录">'
        '<p class="toc-title">本页目录</p>'
        f'<div class="toc-list">{links}</div>'
        "</nav></aside>"
    )


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


# ------------------------------------------------------------- page visuals
# Homepage flow + blind-test chart, and per-page file/token visuals.
# All inline SVG/CSS, no JavaScript libraries, no CDN.

FLOW_HTML = (
    '<div class="flow" role="img" aria-label="建库流程：需求文档、抽种子、调用图一跳、'
    'PageRank 二跳、8000 token 预算、人工确认、知识页">'
    '<span class="step"><span class="step-idx">01</span>需求文档</span><span class="arrow">→</span>'
    '<span class="step"><span class="step-idx">02</span>抽标识符当种子</span><span class="arrow">→</span>'
    '<span class="step"><span class="step-idx">03</span>调用图 1 跳邻居</span><span class="arrow">→</span>'
    '<span class="step"><span class="step-idx">04</span>PageRank 过滤 2 跳</span><span class="arrow">→</span>'
    '<span class="step"><span class="step-idx">05</span>8000 token 截断</span><span class="arrow">→</span>'
    '<span class="step"><span class="step-idx">06</span>人工确认</span><span class="arrow">→</span>'
    '<span class="step strong"><span class="step-idx">07</span>知识页</span></div>'
)

BLIND_SVG = (
    '<svg class="bars" viewBox="0 0 420 78" role="img" '
    'aria-label="盲测召回：3896 题找回 5 个中的 3 个，3878 题找回 4 个中的 2 个">'
    '<text x="0" y="18" class="bar-label">#3896</text>'
    '<rect x="54" y="6" width="296" height="14" rx="7" class="bar-track"/>'
    '<rect x="54" y="6" width="178" height="14" rx="7" class="bar-fill"/>'
    '<text x="360" y="18" class="bar-value">3 / 5</text>'
    '<text x="0" y="54" class="bar-label">#3878</text>'
    '<rect x="54" y="42" width="296" height="14" rx="7" class="bar-track"/>'
    '<rect x="54" y="42" width="148" height="14" rx="7" class="bar-fill"/>'
    '<text x="360" y="54" class="bar-value">2 / 4</text>'
    '</svg>'
    '<p class="muted">召回率：只给需求描述、仓库回到改动前提交，对照真实改动文件；'
    'CHANGES.md 在改动前不存在，可达上限为 4/5 与 3/4，核心改动文件均在清单内。</p>'
)

SEARCH_BOX_HTML = (
    '<div class="search-box">'
    '<svg class="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
    '<input type="search" id="kb-search" class="search-input" '
    'placeholder="筛选知识页、仓库或关键词…" aria-label="筛选知识页">'
    '<span id="kb-search-count" class="search-count"></span>'
    '</div>'
)

_REL_ROW = re.compile(r"^\|\s*\[.*?\]\(.*?\)\s*\|\s*([^|]+?)\s*\|", re.M)
_TOKEN_TOTAL = re.compile(r"约\s*([\d,]+)\s*tokens")


def extract_relation_counts(md: str) -> dict[str, int]:
    """Count files by 关联 column （种子 / 1 跳邻居 / 2 跳邻居）."""
    counts: dict[str, int] = {}
    for m in _REL_ROW.finditer(md):
        rel = m.group(1).strip()
        counts[rel] = counts.get(rel, 0) + 1
    return counts


def extract_token_total(md: str) -> int | None:
    m = _TOKEN_TOTAL.search(md)
    return int(m.group(1).replace(",", "")) if m else None


def page_viz_html(md: str) -> str:
    """Per-page visual summary: file-origin stacked bar + token budget bar."""
    counts = extract_relation_counts(md)
    total = extract_token_total(md)
    if not counts and total is None:
        return ""
    parts: list[str] = ['<div class="page-viz">']
    if counts:
        n = sum(counts.values())
        colors = {"种子": "var(--seed)", "1 跳邻居": "var(--hop1)", "2 跳邻居": "var(--hop2)"}
        segs = "".join(
            f'<span style="width:{c / n * 100:.1f}%;background:{colors.get(k, "var(--muted)")}" '
            f'title="{html.escape(k)} {c} 个"></span>'
            for k, c in counts.items()
        )
        legend_items = "".join(
            '<span class="legend-item">'
            f'<span class="legend-dot" style="background:{colors.get(k, "var(--muted)")}"></span>'
            f'{html.escape(k)} {c} 个</span>'
            for k, c in counts.items()
        )
        parts.append(
            '<div class="viz-block">'
            f'<div class="viz-head"><h3>文件来源分布</h3><span class="viz-stat">共 {n} 个文件</span></div>'
            f'<div class="stackbar">{segs}</div>'
            f'<div class="viz-legend">{legend_items}</div></div>'
        )
    if total is not None:
        pct = min(total / 8000 * 100, 100)
        parts.append(
            '<div class="viz-block">'
            f'<div class="viz-head"><h3>Token 预算占用</h3><span class="viz-stat">{pct:.0f}%</span></div>'
            f'<div class="budgetbar"><span style="width:{pct:.1f}%"></span></div>'
            f'<div class="viz-legend"><span>约 {total:,} / 8,000 tokens（预算内截断）</span></div></div>'
        )
    parts.append("</div>")
    return "".join(parts)


# ------------------------------------------------------------------- build
def render_template(name: str, **kw: str) -> str:
    tpl = (ROOT / "templates" / name).read_text(encoding="utf-8")
    for key, val in kw.items():
        tpl = tpl.replace("{{" + key + "}}", val)
    return tpl


def _render_card(page: dict, href: str, shared_links: list[str], heading_tag: str = "h4") -> str:
    badges = [f'<span class="pill">{page["file_count"]} 个文件</span>']
    if page.get("token_total"):
        badges.append(f'<span class="pill">约 {page["token_total"]:,} tokens</span>')
    if page.get("level"):
        badges.append(f'<span class="pill pill-accent">分级 {html.escape(page["level"])}</span>')
    elif page["shared"]:
        badges.append(f'<span class="pill">{len(page["shared"])} 个关联需求</span>')
    shared_html = (
        '<div class="card-shared"><span>相关需求</span>' + "".join(shared_links) + "</div>"
        if shared_links else ""
    )
    search_blob = " ".join([
        page["id"],
        page["title"],
        page["summary"],
        page["source"]["title"],
        page["source"]["repo_name"],
        " ".join(page["shared"]),
    ]).lower()
    return (
        f'<article class="card" data-search="{html.escape(search_blob, quote=True)}">'
        f'<div class="card-top"><{heading_tag}><a href="{href}">{html.escape(page["title"])}</a></{heading_tag}></div>'
        f'<p class="card-summary">{html.escape(page["summary"])}</p>'
        f'<div class="card-badges">{"".join(badges)}</div>'
        f"{shared_html}</article>"
    )


def build_site(config_path: Path, out_dir: Path, base_url: str) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    generated = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M CST")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "assets").mkdir(parents=True)
    shutil.copy(ROOT / "assets" / "mermaid.min.js", out_dir / "assets" / "mermaid.min.js")
    shutil.copy(ROOT / "templates" / "style.css", out_dir / "assets" / "style.css")
    shutil.copy(ROOT / "templates" / "app.js", out_dir / "assets" / "app.js")

    mermaid_js = '<script src="{{root}}assets/mermaid.min.js"></script>'
    all_pages: list[dict] = []
    l2_urls: list[str] = []
    index_sections: list[str] = []
    grand_total_files = 0
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
        pages_here: list[dict] = []
        total_files = 0
        for req_id in page_ids:
            md_path = md_files.get(req_id)
            if md_path is None:
                print(f"  跳过 {req_id}：index.json 有登记但找不到 md", file=sys.stderr)
                continue
            raw = sanitize(md_path.read_text(encoding="utf-8"))
            title = extract_title(raw)
            body, has_mermaid, headings = md_to_html(raw, strip_first_h1=True)
            toc = toc_html(headings)
            viz = page_viz_html(raw)
            files = index.get(req_id, {}).get("files", [])
            file_count = len(files) or count_table_rows(raw)
            total_files += file_count
            grand_total_files += file_count
            level_m = re.search(r"分级：(\w+)", raw)
            shared = index.get(req_id, {}).get("shared_with", [])
            home_shared_chips = [
                f'<a class="chip" href="{src["id"]}/{o}.html">{html.escape(o)}</a>'
                if o in page_ids else f'<span class="chip">{html.escape(o)}</span>'
                for o in shared
            ]
            local_shared_chips = [
                f'<a class="chip" href="{o}.html">{html.escape(o)}</a>'
                if o in page_ids else f'<span class="chip">{html.escape(o)}</span>'
                for o in shared
            ]
            url = f"{src['id']}/{req_id}.html"
            summary = extract_summary(raw)
            token_total = extract_token_total(raw)
            level = level_m.group(1) if level_m else ""
            page = {
                "id": req_id, "title": title, "source": src,
                "file_count": file_count, "shared": shared,
                "summary": summary, "url": url,
                "token_total": token_total, "level": level,
            }
            all_pages.append(page)
            pages_here.append(page)
            cards.append(_render_card(page, f"{src['id']}/{req_id}.html", home_shared_chips, heading_tag="h4"))

            meta_pills = [
                f'<a class="pill" href="{html.escape(src["repo_url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(src["repo_name"])}</a>',
                f'<span class="pill">{file_count} 个相关文件</span>',
            ]
            if token_total:
                meta_pills.append(f'<span class="pill">约 {token_total:,} tokens</span>')
            if level:
                meta_pills.append(f'<span class="pill pill-accent">分级 {html.escape(level)}</span>')
            if local_shared_chips:
                meta_pills.append(
                    '<span class="muted">相关需求：</span>' + "".join(local_shared_chips)
                )
            crumb = (
                f'<nav class="crumb" aria-label="面包屑导航">'
                f'<a href="../index.html">首页</a><span class="crumb-sep">/</span>'
                f'<a href="index.html">{html.escape(src["title"])}</a><span class="crumb-sep">/</span>'
                f'<span>{html.escape(title)}</span></nav>'
            )
            page_header = (
                f'<div class="page-header">{crumb}'
                f'<h1>{html.escape(title)}</h1>'
                f'<div class="page-meta-row">{"".join(meta_pills)}</div></div>'
            )
            layout_cls = "doc-layout" if toc else "doc-layout no-toc"
            doc_body = (
                f'<div class="{layout_cls}">'
                f'<article class="doc-main">{body}</article>'
                f'{toc}</div>'
            )
            page_html = render_template(
                "base.html",
                title=f"{title} · {src['title']}",
                description=summary or f"{title} 需求代码知识页",
                body_class="page-doc",
                root="../",
                content=page_header + viz + doc_body,
                generated=generated,
                mermaid=mermaid_js.replace("{{root}}", "../") if has_mermaid else "",
            )
            (src_dir / f"{req_id}.html").write_text(page_html, encoding="utf-8")

        # L2 index for this source (the middle layer of the two-level
        # index): one card per page, with token total and level, so a
        # reader can pick a page without loading the homepage's full list.
        l2_cards: list[str] = []
        for p in pages_here:
            l2_shared = [
                f'<a class="chip" href="{o}.html">{html.escape(o)}</a>'
                for o in p["shared"] if o in page_ids
            ]
            l2_cards.append(_render_card(p, f"{p['id']}.html", l2_shared, heading_tag="h3"))

        l2_html = render_template(
            "base.html",
            title=f"{src['title']} · 全部知识页",
            description=src.get("blurb", f"{src['title']} 需求知识库目录"),
            body_class="page-source",
            root="../",
            content=(
                '<div class="l2-hero">'
                f'<nav class="crumb" aria-label="面包屑导航"><a href="../index.html">首页</a>'
                f'<span class="crumb-sep">/</span><span>{html.escape(src["title"])}</span></nav>'
                f'<h1>{html.escape(src["title"])}</h1>'
                f'<p class="lead">{html.escape(src.get("blurb", ""))}</p>'
                f'<div class="page-meta-row">'
                f'<a class="pill pill-accent" href="{html.escape(src["repo_url"], quote=True)}" target="_blank" rel="noopener noreferrer">源仓库 {html.escape(src["repo_name"])} ↗</a>'
                f'<span class="pill">{len(pages_here)} 份知识页</span>'
                f'<span class="pill">共 {total_files} 个文件</span>'
                '</div></div>'
                '<div class="catalog-head">'
                '<div><h2>全部知识页</h2></div>'
                + SEARCH_BOX_HTML +
                '</div>'
                f'<section class="source-section"><div class="cards">{"".join(l2_cards)}</div></section>'
                '<div id="kb-search-empty" class="empty-state" hidden>没有匹配的知识页，换个关键词试试。</div>'
            ),
            generated=generated,
            mermaid="",
        )
        (src_dir / "index.html").write_text(l2_html, encoding="utf-8")
        l2_urls.append(f"{src['id']}/")
        index_sections.append(
            f'<section class="source-section" id="{src["id"]}">'
            f'<div class="source-header"><h3>{html.escape(src["title"])}</h3>'
            f'<a class="source-all-link" href="{src["id"]}/index.html">查看全部 {len(cards)} 页 →</a></div>'
            f'<p class="source-blurb">{html.escape(src.get("blurb", ""))}</p>'
            f'<div class="source-meta">'
            f'<span>源仓库：<a href="{html.escape(src["repo_url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(src["repo_name"])}</a></span>'
            f'<span>·</span><span>{len(cards)} 页</span>'
            f'<span>·</span><span>共 {total_files} 个文件</span></div>'
            f'<div class="cards">{"".join(cards)}</div></section>'
        )

    hero = (
        '<section class="hero">'
        '<p class="hero-kicker">Requirement-Driven Code Knowledge Base</p>'
        '<h1>需求代码知识库</h1>'
        '<p class="lead"><strong>req-code-kb</strong>（requirement · code · knowledge base）：'
        '按需求构建“最小完备上下文”——做一道菜只备齐这道菜要用的料，不把整个仓库倒给读者或大模型。</p>'
        '<div class="hero-actions">'
        '<a class="btn btn-primary" href="#catalog">浏览全部知识页 ↓</a>'
        '<a class="btn btn-secondary" href="https://github.com/zhanglunet/req-code-kb" target="_blank" rel="noopener noreferrer">查看工具仓库</a>'
        '</div>'
        '<div class="stats-strip">'
        f'<div class="stat-item"><span class="stat-value">{len(config["sources"])}</span><span class="stat-label">已接入源仓库</span></div>'
        f'<div class="stat-item"><span class="stat-value">{len(all_pages)}</span><span class="stat-label">沉淀知识页</span></div>'
        f'<div class="stat-item"><span class="stat-value">{grand_total_files}</span><span class="stat-label">关联代码文件</span></div>'
        '<div class="stat-item"><span class="stat-value">8,000</span><span class="stat-label">单页 Token 预算上限</span></div>'
        '</div></section>'
    )

    pillars = (
        '<section class="pillars" aria-label="核心特性">'
        '<div class="pillar"><span class="pillar-num">01 · 这是什么</span>'
        '<h2>按需求挑出最小完备上下文</h2>'
        '<p>零依赖 Python 工具，融合代码仓库、需求文档与群消息三路来源，给每个需求沉淀刚好够讲清楚、改得动、验得过的知识页。</p></div>'
        '<div class="pillar"><span class="pillar-num">02 · 解决什么问题</span>'
        '<h2>告别整仓倒灌与噪声淹没</h2>'
        '<p>把“找相关文件”做成可重复流程：抽标识符当种子，沿调用图取 1 跳邻居，按 PageRank 筛 2 跳，8000 tokens 预算截断并人工确认。</p></div>'
        '<div class="pillar"><span class="pillar-num">03 · 一页里有什么</span>'
        '<h2>从需求原文到回流记录</h2>'
        '<p>包含需求原文、精确到提交的相关文件表、Mermaid 调用链图、影响面、群消息佐证与验收清单；做完后真实改动记回页末。</p></div>'
        '</section>'
    )

    catalog = (
        '<section id="catalog">'
        '<div class="catalog-head">'
        '<div><h2>知识库目录</h2>'
        '<p class="muted">按来源仓库组织，支持关键词即时筛选</p></div>'
        + SEARCH_BOX_HTML +
        '</div>'
        + "".join(index_sections) +
        '<div id="kb-search-empty" class="empty-state" hidden>没有匹配的知识页，换个关键词试试。</div>'
        '</section>'
    )

    methodology = (
        '<section class="method-section" id="how-it-works">'
        '<h2>建库流程与盲测验证</h2>'
        '<p class="muted">新需求进来重复同一套命令即可沉淀入站，无需手写任何 HTML。</p>'
        '<div class="method-grid">'
        '<div class="panel">'
        '<h3>怎么用：从需求文档到知识页</h3>'
        '<p>按需求大小选分级（<code>--level full</code> 完整、<code>lite</code> 轻量、<code>vibe</code> 随手），沉淀后重跑生成器自动入站。</p>'
        + FLOW_HTML +
        '<div class="cmd-list">'
        '<div class="cmd-item"><code>reqkb build</code><span>抽取最小上下文并沉淀知识页</span></div>'
        '<div class="cmd-item"><code>reqkb ask</code><span>检索知识库并拼接提示词</span></div>'
        '<div class="cmd-item"><code>reqkb eval</code><span>运行盲测检验文件召回率</span></div>'
        '<div class="cmd-item"><code>reqkb harvest</code><span>把真实改动回流记入知识页</span></div>'
        '</div></div>'
        '<div class="panel">'
        '<h3>凭什么可信：pallets/click 盲测</h3>'
        '<p>拿两个已合并 PR 当考题，仅输入需求描述、仓库回到改动前提交，对照真实改动文件。详见'
        '<a href="https://github.com/zhanglunet/req-code-kb/blob/main/docs/mvp-plan.md" target="_blank" rel="noopener noreferrer">盲测方法说明</a>。</p>'
        + BLIND_SVG +
        '</div></div></section>'
    )

    home = render_template(
        "base.html",
        title="首页",
        description="req-code-kb 需求代码知识库：按需求构建最小完备上下文，结合调用图与 PageRank 沉淀结构化代码知识页。",
        body_class="page-home",
        root="",
        content=hero + pillars + catalog + methodology,
        generated=generated,
        mermaid="",
    )
    (out_dir / "index.html").write_text(home, encoding="utf-8")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{base_url}/</loc></url>\n"
        + "".join(
            f"  <url><loc>{base_url}/{u}</loc></url>\n" for u in l2_urls
        )
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
