"""TF-IDF retrieval + requirement seeds + budget cut.

Same retrieval family as the FDE bot (TF-IDF, no embeddings, no
network): a word that is rare across the repo but common in one file
is a strong pointer to that file -- like shouting a full name plus
employee ID in a crowd instead of shouting "Zhang Wei".
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .graph import Node, build_graph, file_scores, pagerank, reverse_edges
from .parse import FileInfo

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "with",
    "on", "is", "are", "be", "by", "as", "at", "from", "this", "that",
    "it", "its", "can", "should", "will", "would", "not", "no", "use",
    "used", "using", "into", "when", "then", "than", "also", "more",
    "such", "was", "were", "have", "has", "had", "if", "else", "but",
    "do", "does", "did", "so", "we", "you", "they", "them", "their",
    "there", "here", "which", "what", "how", "why", "all", "any",
    "each", "both", "between", "over", "under", "out", "up", "down",
    "new", "old", "one", "two", "first", "second", "may", "might",
}

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_QUALIFIED_REF_RE = re.compile(r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?:\(\))?")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_FILE_NAME_SCORE = 5.0


def split_markdown_sections(lines: list[str]) -> list[dict]:
    """Split Markdown lines into h2 sections (issue #12).

    One section per ``## `` heading: the heading line plus everything
    up to (not including) the next ``## `` heading. Each section
    carries its title path (h1 + h2, e.g. "Testing Click
    Applications / Context Settings") and 1-based start/end lines,
    so a hit can point back at the exact section -- the survey's
    borrow #1 ("chunks carry title path + start/end line numbers").

    Rules, kept deliberately small:
    - ``# `` sets the title-path prefix only; it does not start a
      section. ``### `` and deeper stay inside their h2 section.
    - Headings inside fenced code blocks (``` / ~~~) are ignored.
    - Text before the first ``## `` is not a section: the whole-file
      cosine still covers it, so nothing is ever lost from scoring.
    - A file with no ``## `` heading has no sections.
    """
    h1 = ""
    sections: list[dict] = []
    cur: dict | None = None
    in_fence = False
    for i, line in enumerate(lines, 1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        if not in_fence:
            m = _HEADING_RE.match(line)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                if level == 1:
                    h1 = title
                    if cur is not None:
                        cur["text"] += line + "\n"
                    continue
                if level == 2 and title:
                    if cur is not None:
                        cur["end_line"] = i - 1
                        sections.append(cur)
                    cur = {
                        "heading": title,
                        "title_path": f"{h1} / {title}" if h1 else title,
                        "start_line": i,
                        "end_line": len(lines),
                        "text": line + "\n",
                    }
                    continue
        if cur is not None:
            cur["text"] += line + "\n"
    if cur is not None:
        cur["end_line"] = len(lines)
        sections.append(cur)
    return sections


def tokenize(text: str) -> list[str]:
    """Split identifiers on underscores and camelCase humps.

    ASCII identifiers split as before. Chinese runs contribute single
    characters and bigrams (prefixed so they never collide with ASCII
    tokens): without them a Chinese question tokenizes to nothing and
    retrieval scores only the backticked identifiers, so a plain
    Chinese question ("这个仓库有哪些主要模块？") finds no hits at all
    (observed on CLI-Anything, 2026-11-24).
    """
    out: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        parts = re.split(r"_", raw)
        for part in parts:
            for piece in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", part):
                token = piece.lower()
                if len(token) >= 2 and token not in STOPWORDS:
                    out.append(token)
    for run in _CJK_RE.findall(text):
        for ch in run:
            out.append("zh_" + ch)
        for i in range(len(run) - 1):
            out.append("zh_" + run[i:i + 2])
    return out


def extract_seed_identifiers(req_text: str) -> list[str]:
    """Identifiers the requirement names in backticks, in order.

    A dotted span like `CliRunner.invoke` yields *both* parts: the
    class is as much a seed as the method, and dropping it (keeping
    only the last part) loses the most specific signal in the doc.
    """
    seeds: list[str] = []
    for span in _BACKTICK_RE.findall(req_text):
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", span):
            for part in token.split("."):
                if len(part) >= 2 and part not in seeds:
                    seeds.append(part)
    return seeds


def _qualified_references(text: str) -> set[str]:
    """Preserve dotted API names in inline code, ignoring empty call parentheses."""
    return {
        match[1]
        for span in _BACKTICK_RE.findall(text)
        if (match := _QUALIFIED_REF_RE.fullmatch(span.strip()))
    }


class TfIdfIndex:
    def __init__(self, files: dict[str, FileInfo]) -> None:
        self.files = files
        self.doc_tokens: dict[str, Counter] = {}
        self.idf: dict[str, float] = {}
        # h2 sections of Markdown files, precomputed once: each section
        # carries its title path + line range + token counter, so
        # scoring a section is a cheap vector lookup, not a re-tokenize.
        self.sections: dict[str, list[dict]] = {}
        # Per-query winners, filled by score_files: path -> section
        # (heading, title_path, start_line, end_line) when the section
        # is what made the file score.
        self.section_hits: dict[str, dict] = {}
        doc_count = len(files)
        df: Counter = Counter()
        for path, info in files.items():
            tokens = tokenize(info.text)
            # Symbol names count triple: a file defining CliRunner *is*
            # about CliRunner more than a file merely mentioning it.
            for qualname in info.symbols:
                tokens += tokenize(qualname) * 3
            counter = Counter(tokens)
            self.doc_tokens[path] = counter
            for token in counter:
                df[token] += 1
            if not info.is_code:
                self.sections[path] = [
                    {
                        "heading": sec["heading"],
                        "title_path": sec["title_path"],
                        "start_line": sec["start_line"],
                        "end_line": sec["end_line"],
                        "counter": Counter(tokenize(sec["text"])),
                        "api_refs": _qualified_references(sec["text"]),
                    }
                    for sec in split_markdown_sections(info.lines)
                ]
        for token, freq in df.items():
            self.idf[token] = math.log((1 + doc_count) / (1 + freq)) + 1.0

    def vector(self, tokens: list[str]) -> dict[str, float]:
        counter = Counter(tokens)
        total = sum(counter.values()) or 1
        return {
            token: (count / total) * self.idf.get(token, 1.0)
            for token, count in counter.items()
        }

    def cosine(self, query_vec: dict[str, float], path: str) -> float:
        doc_vec = self.vector(list(self.doc_tokens[path].elements()))
        common = set(query_vec) & set(doc_vec)
        if not common:
            return 0.0
        dot = sum(query_vec[t] * doc_vec[t] for t in common)
        qnorm = math.sqrt(sum(v * v for v in query_vec.values())) or 1.0
        dnorm = math.sqrt(sum(v * v for v in doc_vec.values())) or 1.0
        return dot / (qnorm * dnorm)

    def chunk_cosine(self, query_vec: dict[str, float], path: str) -> float:
        """Best 50-line window cosine.

        Whole-file cosine dilutes long files: a 1500-line test module
        whose CliRunner colour tests sit in one dense region scores
        lower than a short file that merely mentions the same words.
        The context is fragments, so the file score should reflect
        its densest region, not its average.
        """
        info = self.files[path]
        best = 0.0
        window = 50
        lines = info.lines or [""]
        for start in range(0, len(lines), window):
            chunk_tokens = tokenize("\n".join(lines[start:start + window]))
            if not chunk_tokens:
                continue
            chunk_vec = self.vector(chunk_tokens)
            common = set(query_vec) & set(chunk_vec)
            if not common:
                continue
            dot = sum(query_vec[t] * chunk_vec[t] for t in common)
            qnorm = math.sqrt(sum(v * v for v in query_vec.values())) or 1.0
            cnorm = math.sqrt(sum(v * v for v in chunk_vec.values())) or 1.0
            best = max(best, dot / (qnorm * cnorm))
        return best

    def section_cosine(self, query_vec: dict[str, float], path: str,
                       api_refs: set[str] | None = None) -> tuple[float, dict | None]:
        """Best h2-section cosine for a Markdown file (issue #12).

        Whole-file cosine dilutes long docs: a 300-line doc whose
        answer sits in one 30-line section scores like the average of
        the whole file. The best section is the densest region *with a
        topic boundary*, so it beats both the whole file and the
        arbitrary 50-line window when the answer is section-shaped.
        Returns (best cosine, winning section) or (0.0, None) when the
        file has no h2 sections or no section shares a token with the
        query. Code files have no sections and always return (0.0,
        None). A qualified API reference breaks a lexical score tie.
        """
        best = 0.0
        best_sec: dict | None = None
        best_key = (-1.0, False)
        for sec in self.sections.get(path, ()):
            sec_vec = self.vector(list(sec["counter"].elements()))
            common = set(query_vec) & set(sec_vec)
            if not common:
                continue
            dot = sum(query_vec[t] * sec_vec[t] for t in common)
            qnorm = math.sqrt(sum(v * v for v in query_vec.values())) or 1.0
            snorm = math.sqrt(sum(v * v for v in sec_vec.values())) or 1.0
            cos = dot / (qnorm * snorm)
            key = (round(cos, 9), bool(api_refs and api_refs & sec["api_refs"]))
            if key > best_key:
                best = cos
                best_sec = sec
                best_key = key
        if best_sec is None:
            return 0.0, None
        return best, {
            "heading": best_sec["heading"],
            "title_path": best_sec["title_path"],
            "start_line": best_sec["start_line"],
            "end_line": best_sec["end_line"],
        }


def score_files(files: dict[str, FileInfo], index: TfIdfIndex,
                req_text: str, seeds: list[str]) -> dict[str, float]:
    """File score = seed-symbol bonus + TF-IDF cosine."""
    query_vec = index.vector(tokenize(req_text))
    scores: dict[str, float] = {}
    seed_set = set(seeds)
    api_refs = _qualified_references(req_text)
    # Fresh query, fresh section winners: a second call with a
    # different requirement must not keep the previous query's anchors.
    index.section_hits = {}
    for path, info in files.items():
        # The file score reflects its densest region, not its average:
        # for Markdown that region is a whole h2 section, which beats
        # both the whole file and the arbitrary 50-line window when
        # the answer is section-shaped (issue #12).
        whole = index.cosine(query_vec, path)
        chunk = index.chunk_cosine(query_vec, path)
        section, sec_hit = index.section_cosine(query_vec, path, api_refs)
        sim = max(whole, chunk, section)
        section_bonus = 0.0
        # A reference in a diffuse section (e.g. release notes covering
        # many APIs) should keep its ordinary file/50-line-window score.
        if sec_hit is not None and api_refs and round(section, 9) == round(sim, 9):
            lines = info.lines[sec_hit["start_line"] - 1:sec_hit["end_line"]]
            if api_refs & _qualified_references("\n".join(lines)):
                # One exact API reference is comparable to a seed definition.
                # Count it once so repeated examples cannot multiply the boost.
                section_bonus = 5.0
        if sec_hit is not None and (section_bonus or section > max(whole, chunk)):
            # The section is what made the file score: carry its
            # anchor so the page can point at the exact section.
            index.section_hits[path] = sec_hit
        score = sim * 10.0 + section_bonus
        defined = {q.split(".")[-1] for q in info.symbols}
        hits = seed_set & defined
        score += 5.0 * len(hits)
        # The file *uses* a seed symbol (calls it): test files exercise
        # CliRunner.invoke without defining it, so they need credit too.
        called = {name for calls in info.calls.values() for name, _ in calls}
        score += 2.0 * len(seed_set & called)
        # Backtick identifiers inside the file (docs quote `CliRunner.invoke()`)
        # count as a mention of the seed.
        quoted = set(extract_seed_identifiers(info.text))
        score += 3.0 * len(seed_set & quoted)
        if _file_stem(path) in seed_set:
            score += _FILE_NAME_SCORE
        scores[path] = score
    return scores


class Context:
    """The minimal complete context for one requirement."""

    def __init__(self, req_id: str, req_text: str) -> None:
        self.req_id = req_id
        self.req_text = req_text
        self.seeds: list[str] = extract_seed_identifiers(req_text)
        self.files: list[dict] = []  # {path, score, symbols, tokens}
        self.total_tokens = 0
        self.hops: dict[str, int] = {}  # file -> hop distance from a seed
        self.level = "full"
        # Impact analysis: seed file -> top callers of its seed symbols
        # ("caller_path:caller_symbol"), i.e. what breaks if you touch it.
        self.impact: dict[str, list[str]] = {}

    def file_paths(self) -> list[str]:
        return [f["path"] for f in self.files]


# Demand levels (borrowed from the AIspec article's Full/Lite/Vibe
# classification, adapted to this tool): how deep the retrieval goes
# depends on how big the change is, so a one-line fix doesn't pay the
# full-context price. full is exactly the old default behaviour.
LEVELS: dict[str, dict] = {
    "full": {"budget": 8000, "max_files": 10, "per_file_symbols": 5,
             "per_file_tokens": 1200, "max_hops": 2,
             "label": "完整（跨多文件、核心逻辑）"},
    "lite": {"budget": 4000, "max_files": 6, "per_file_symbols": 4,
             "per_file_tokens": 1000, "max_hops": 1,
             "label": "轻量（单模块小修、简单 CRUD）"},
    "vibe": {"budget": 2000, "max_files": 4, "per_file_symbols": 3,
             "per_file_tokens": 800, "max_hops": 0,
             "label": "随手（文字、配置、UI 样式）"},
}


def _file_stem(path: str) -> str:
    """Filename without directory or extension ("" for extensionless)."""
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


def _stem_matches_seed(stem: str, seeds: set[str]) -> bool:
    """Does the requirement name this file -- exactly, or by prefix?

    Exact: `skill_generator.py` for the seed `skill_generator`.
    Prefix: `installer.py` for the seed `install` -- the requirement
    names the `install` command, the file is the thing that installs.
    The 6-character minimum keeps generic seeds (`test`, `docs`,
    `SKILL`, `cli`) from matching everything.
    """
    return any(len(s) >= 6 and stem.startswith(s) for s in seeds)


def _defined_seeds(info: FileInfo, seeds: set[str]) -> set[str]:
    """Seed symbols this file defines, specific ones only.

    Short seeds (`cli`, `test`) match half the repo -- every CLI module
    defines a `cli` object -- so a defined symbol only counts when it
    is at least 6 characters (`ReplSkin`, `invoke`, `preview`).
    """
    return {
        s
        for s in ({q.split(".")[-1] for q in info.symbols} & seeds)
        if len(s) >= 6
    }


def _is_seed_named(path: str, info: FileInfo, seeds: set[str]) -> bool:
    """Does this file carry a seed in its name or its definitions?

    A file that *defines* the thing the requirement names (or is named
    after it) is the thing itself, not a bystander that merely mentions
    it -- so it gets a floor in the ranking below, and can't lose to a
    test file that only calls the seed. The 6-character minimum keeps
    generic seeds (`test`, `SKILL`, `docs`, `cli`) from promoting
    everything.
    """
    if _stem_matches_seed(_file_stem(path), seeds):
        return True
    return bool(_defined_seeds(info, seeds))


def build_context(files: dict[str, FileInfo], req_id: str, req_text: str,
                  budget_tokens: int | None = None,
                  level: str = "full") -> Context:
    """Seeds -> 1-hop neighbours (always) -> 2-hop by PageRank -> budget cut.

    level picks the depth: full goes 2 hops, lite 1 hop, vibe seeds only.
    budget_tokens overrides the level's budget when given explicitly.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r} (full/lite/vibe)")
    cfg = LEVELS[level]
    budget = budget_tokens if budget_tokens is not None else cfg["budget"]
    max_files = cfg["max_files"]
    per_file_symbols = cfg["per_file_symbols"]
    per_file_tokens = cfg["per_file_tokens"]
    max_hops = cfg["max_hops"]
    ctx = Context(req_id, req_text)
    ctx.level = level
    index = TfIdfIndex(files)
    scores = score_files(files, index, req_text, ctx.seeds)
    nodes, edges = build_graph(files)
    rank = pagerank(nodes, edges)
    fscores = file_scores(files, rank)

    # Seed files: files that define a seed symbol, plus top TF-IDF hits,
    # plus files whose name is a seed -- exactly (`repl_skin.py` for
    # `ReplSkin`, `docs/PREVIEW_PROTOCOL.md` for `PREVIEW_PROTOCOL`) or
    # by prefix (`installer.py` for the `install` command). Short seeds
    # like `test`, `docs`, `SKILL` match dozens of unrelated files and
    # would flood the list, so the name rule needs a 6-character seed.
    # vibe keeps only seed files (defining + name-matched), no TF-IDF
    # top-5: a one-line fix shouldn't drag in "probably relevant" files.
    seed_files = {
        path for path, info in files.items() if _defined_seeds(info, set(ctx.seeds))
    }
    seed_files.update(
        path for path in files
        if _stem_matches_seed(_file_stem(path), set(ctx.seeds))
    )
    if level != "vibe":
        top_tfidf = sorted(scores, key=lambda p: (-scores[p], p))[:5]
        seed_files.update(p for p in top_tfidf if scores[p] > 0)
    for path in seed_files:
        ctx.hops[path] = 0

    # Symbol-level neighbourhoods.
    seed_nodes = {
        node for node in nodes
        if node[1].split(".")[-1] in set(ctx.seeds)
    }
    callers = reverse_edges(edges)

    def neighbour_files(seed_set: set[Node], hops: int) -> dict[str, int]:
        found: dict[str, int] = {}
        frontier = set(seed_set)
        for distance in range(1, hops + 1):
            nxt: set[Node] = set()
            for node in frontier:
                for nb in list(edges.get(node, ())) + list(callers.get(node, ())):
                    nxt.add(nb)
                    if nb[0] not in found and nb[0] not in ctx.hops:
                        found[nb[0]] = distance
            frontier = nxt
        return found

    if max_hops >= 1:
        one_hop = neighbour_files(seed_nodes, 1)
        ctx.hops.update(one_hop)
    if max_hops >= 2:
        two_hop = neighbour_files(seed_nodes, 2)
        two_hop = {p: d for p, d in two_hop.items() if p not in ctx.hops}
        if two_hop:
            # 2-hop files only survive if their PageRank is above the median
            # of the 2-hop candidates.
            ranked = sorted(two_hop, key=lambda p: fscores.get(p, 0.0), reverse=True)
            keep = set(ranked[: max(1, len(ranked) // 2)])
            two_hop = {p: d for p, d in two_hop.items() if p in keep}
        ctx.hops.update(two_hop)

    # Rank every candidate file by retrieval score, then cut by budget.
    # Fragments are the file's seed / neighbour symbols, not whole files:
    # a whole testing.py alone would eat the budget. Per file we keep
    # at most 8 symbols / 2500 tokens, seed symbols first, then the
    # highest-PageRank neighbours; at most 10 files in total.
    # Seed-named files get a bonus in the walk, not an absolute tier.
    # Without a floor a file that *defines* the seed loses to test
    # files that merely call it -- in one real run on CLI-Anything,
    # `repl_skin.py` (defines `ReplSkin`) ranked 388th by score and
    # never made the cut, while its callers did. But strict tiers
    # misorder the other way: a low-scoring exact-name file (such as
    # `eth2/.../install.py`) can outrank evidence from the hub itself.
    # Cap that bonus using evidence beyond the filename match.
    # One file per stem in the floor group: a monorepo holds dozens of
    # copies of the same named file (63 repl_skin.py, 7 HARNESS.md);
    # keep the shallowest (the plugin's own, not an app's copy), then
    # the highest score. The copies are dropped from the walk, not
    # demoted: a demoted copy would re-enter right behind on score
    # (safari's HARNESS.md scores 47) and eat the budget again.
    seed_set = set(ctx.seeds)
    named_paths = {span.strip().removeprefix("./") for span in _BACKTICK_RE.findall(req_text)}
    floor_set = {
        p for p in ctx.hops if _is_seed_named(p, files[p], seed_set)
    }
    keep_floor: dict[tuple[str | None, str], str] = {}

    def name_priority(path: str) -> int:
        if path in named_paths:
            return 0
        if path.rsplit("/", 1)[-1] in named_paths:
            return 1
        return 2

    def floor_priority(path: str) -> tuple[int, int, float, str]:
        return (name_priority(path), path.count("/"), -round(scores[path], 9), path)

    for p in floor_set:
        # Hand-written code in different languages can intentionally
        # share a stem (for example a deployment script and its SQL).
        language = files[p].language
        key = (None if language == "python" else language, _file_stem(p))
        current = keep_floor.get(key)
        if current is None or floor_priority(p) < floor_priority(current):
            keep_floor[key] = p
    keep_floor_set = set(keep_floor.values())

    def _floor_tier(path: str) -> int:
        """How strongly does the requirement name this file?

        0 -- the filename *is* a seed (`skill_generator.py`).
        1 -- the file *defines* a seed symbol (`ui.py` defines
             `ReplSkin`).
        2 -- the filename merely *starts with* a seed
             (`installer.py` for `install`, `matrix_skill.py` for
             `matrix`). A prefix is a weak signal: `search_members.py`
             also starts with `search`, and it is just an app command.
        """
        stem = _file_stem(path)
        if stem in seed_set and len(stem) >= 6:
            return 0
        if _defined_seeds(files[path], seed_set):
            return 1
        if _stem_matches_seed(stem, seed_set):
            return 2
        return 3

    candidates = [
        p for p in ctx.hops if p not in floor_set or p in keep_floor_set
    ]
    # Every sort below ends in a name tiebreak (and ranks are rounded
    # to 9 decimals first): the graph is built from sets, so PageRank
    # ties and even last-bit float noise would otherwise make the same
    # input produce a different page on the next run -- the demo
    # rehearsal caught it (same file list, different symbols, 7445 vs
    # 7951 tokens). A build must be reproducible byte for byte.
    def _walk_bonus(path: str) -> float:
        """Reward exact names in proportion to their independent evidence."""
        if path not in keep_floor_set:
            return 0.0
        tier = _floor_tier(path)
        if tier == 0:
            if name_priority(path) < 2:
                return 55.0
            # Keep the full +55 for repl_skin.py (raw 10.7) while giving
            # install.py (raw 5.06) almost no additional boost.
            evidence = max(0.0, scores[path] - _FILE_NAME_SCORE)
            return min(55.0, 10.0 * evidence)
        return {1: 10.0, 2: 5.0}.get(tier, 0.0)

    candidates.sort(
        key=lambda p: (-(scores.get(p, 0.0) + _walk_bonus(p)), p),
    )
    # Translated copies of the same document (README.md / README_CN.md /
    # README_DE.md / ...) say the same thing in different languages and
    # each scores as high as the original; without dedup they crowd the
    # budget out (5 variants x 1500 tokens = 7500 of 8000 in one real
    # run on CLI-Anything, 2026-11-24). Keep only the best-scoring file
    # per doc family (same directory, same stem before a language suffix).
    def _doc_family(path: str) -> str | None:
        if not path.endswith(".md"):
            return None
        directory, _, filename = path.rpartition("/")
        stem = filename[:-3]
        base = re.sub(r"_[A-Za-z]{2}$", "", stem)
        return f"{directory}/{base}"

    seen_families: set[str] = set()
    deduped: list[str] = []
    for path in candidates:
        family = _doc_family(path)
        if family is None or family not in seen_families:
            deduped.append(path)
            if family is not None:
                seen_families.add(family)
    candidates = deduped
    sql_query_terms = set(tokenize(req_text)) if any(
        files[path].language == "sql" for path in candidates
    ) else set()
    for path in candidates:
        if len(ctx.files) >= max_files:
            break
        if ctx.total_tokens >= budget:
            break
        info = files[path]
        wanted = {
            q for q in info.symbols
            if q.split(".")[-1] in set(ctx.seeds)
            or (path, q) in seed_nodes
            or any((path, q) in edges.get(n, ()) or (path, q) in callers.get(n, ())
                   for n in seed_nodes)
        }
        statement_scores: dict[str, int] = {}
        if info.language == "sql":
            # Statements such as SELECT have synthetic names. Include
            # relevant statements even if a named DDL symbol already matched.
            for q in info.symbols:
                _, _, snippet = info.snippet(q)
                matches = len(sql_query_terms.intersection(tokenize(snippet)))
                if matches:
                    statement_scores[q] = matches
            best_statements = sorted(statement_scores, key=lambda q: (-statement_scores[q], q))
            wanted.update(best_statements[:3])
        if not wanted:
            if info.is_code:
                # Seed file with no matching symbol (e.g. a test module
                # that gets its runner from a fixture): contribute its
                # highest-PageRank symbols instead of nothing.
                ranked_all = sorted(
                    info.symbols,
                    key=lambda q: (-round(rank.get((path, q), 0.0), 9), q),
                )
                wanted = set(ranked_all[:3])
            else:
                wanted = set()
        ranked_syms = sorted(
            wanted,
            key=lambda q: (
                0 if q.split(".")[-1] in set(ctx.seeds) else 1,
                -statement_scores.get(q, 0),
                -round(rank.get((path, q), 0.0), 9),
                q,
            ),
        )[:per_file_symbols]
        symbols = []
        tokens = 0
        for qualname in ranked_syms:
            start, end, text = info.snippet(qualname)
            frag_tokens = max(1, len(text) // 4)
            if tokens + frag_tokens > per_file_tokens:
                continue
            if ctx.total_tokens + tokens + frag_tokens > budget:
                continue
            tokens += frag_tokens
            callees = sorted({
                dst[1].split(".")[-1]
                for dst in edges.get((path, qualname), ())
            })[:5]
            symbols.append({
                "name": qualname, "line": start, "end_line": end,
                "snippet": text, "tokens": frag_tokens,
                "callees": callees,
            })
        if not info.is_code:
            tokens = min(info.token_estimate, 1500)
        if ctx.total_tokens + tokens > budget:
            continue
        if not symbols and tokens == 0:
            continue  # contributes nothing to the context; skip it
        entry = {
            "path": path, "score": round(scores.get(path, 0.0), 3),
            "hop": ctx.hops[path], "symbols": symbols, "tokens": tokens,
        }
        sec = index.section_hits.get(path)
        if sec is not None:
            # The winning h2 section: the page points at it, not at
            # the top of the file (issue #12).
            entry["section"] = sec
        ctx.files.append(entry)
        ctx.total_tokens += tokens
    _compute_impact(ctx, nodes, edges, rank)
    return ctx


def _compute_impact(ctx: Context, nodes: set[Node],
                    edges: dict[Node, set[Node]],
                    rank: dict[Node, float]) -> None:
    """For each seed file, who calls its seed symbols (blast radius).

    Only seed files get an impact list: they are the files the change
    touches first, so their callers are the first thing that can break.
    Top 3 caller files per seed file, ranked by the caller's PageRank.
    """
    callers = reverse_edges(edges)
    seed_nodes = {
        node for node in nodes
        if node[1].split(".")[-1] in set(ctx.seeds)
    }
    per_file: dict[str, dict[str, float]] = {}
    for callee in seed_nodes:
        for caller in callers.get(callee, ()):
            per_file.setdefault(callee[0], {})[caller] = rank.get(caller, 0.0)
    for path, caller_ranks in per_file.items():
        top = sorted(
            caller_ranks,
            key=lambda c: (-round(caller_ranks[c], 9), c[0], c[1]),
        )[:3]
        ctx.impact[path] = [f"{c[0]}:{c[1]}" for c in top]
