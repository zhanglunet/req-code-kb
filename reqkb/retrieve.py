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

from .graph import Node, build_graph, file_scores, pagerank
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


def tokenize(text: str) -> list[str]:
    """Split identifiers on underscores and camelCase humps."""
    out: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        parts = re.split(r"_", raw)
        for part in parts:
            for piece in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", part):
                token = piece.lower()
                if len(token) >= 2 and token not in STOPWORDS:
                    out.append(token)
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


class TfIdfIndex:
    def __init__(self, files: dict[str, FileInfo]) -> None:
        self.files = files
        self.doc_tokens: dict[str, Counter] = {}
        self.idf: dict[str, float] = {}
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


def score_files(files: dict[str, FileInfo], index: TfIdfIndex,
                req_text: str, seeds: list[str]) -> dict[str, float]:
    """File score = seed-symbol bonus + TF-IDF cosine."""
    query_vec = index.vector(tokenize(req_text))
    scores: dict[str, float] = {}
    seed_set = set(seeds)
    for path, info in files.items():
        sim = max(index.cosine(query_vec, path),
                  index.chunk_cosine(query_vec, path))
        score = sim * 10.0
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
        if path.rsplit(".", 1)[0].rsplit("/", 1)[-1] in seed_set:
            score += 5.0  # file name itself is named by the requirement
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

    def file_paths(self) -> list[str]:
        return [f["path"] for f in self.files]


def build_context(files: dict[str, FileInfo], req_id: str, req_text: str,
                  budget_tokens: int = 8000) -> Context:
    """Seeds -> 1-hop neighbours (always) -> 2-hop by PageRank -> budget cut."""
    ctx = Context(req_id, req_text)
    index = TfIdfIndex(files)
    scores = score_files(files, index, req_text, ctx.seeds)
    nodes, edges = build_graph(files)
    rank = pagerank(nodes, edges)
    fscores = file_scores(files, rank)

    # Seed files: files that define a seed symbol, plus top TF-IDF hits.
    seed_files = {
        path for path, info in files.items()
        if {q.split(".")[-1] for q in info.symbols} & set(ctx.seeds)
    }
    top_tfidf = sorted(scores, key=scores.get, reverse=True)[:5]
    seed_files.update(p for p in top_tfidf if scores[p] > 0)
    for path in seed_files:
        ctx.hops[path] = 0

    # Symbol-level neighbourhoods.
    seed_nodes = {
        node for node in nodes
        if node[1].split(".")[-1] in set(ctx.seeds)
    }
    callers: dict[Node, set[Node]] = {n: set() for n in nodes}
    for src, dsts in edges.items():
        for dst in dsts:
            callers[dst].add(src)

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

    one_hop = neighbour_files(seed_nodes, 1)
    two_hop = neighbour_files(seed_nodes, 2)
    two_hop = {p: d for p, d in two_hop.items() if p not in one_hop}
    if two_hop:
        # 2-hop files only survive if their PageRank is above the median
        # of the 2-hop candidates.
        ranked = sorted(two_hop, key=lambda p: fscores.get(p, 0.0), reverse=True)
        keep = set(ranked[: max(1, len(ranked) // 2)])
        two_hop = {p: d for p, d in two_hop.items() if p in keep}
    ctx.hops.update(one_hop)
    ctx.hops.update(two_hop)

    # Rank every candidate file by retrieval score, then cut by budget.
    # Fragments are the file's seed / neighbour symbols, not whole files:
    # a whole testing.py alone would eat the budget. Per file we keep
    # at most 8 symbols / 2500 tokens, seed symbols first, then the
    # highest-PageRank neighbours; at most 10 files in total.
    max_files = 10
    per_file_symbols = 5
    per_file_tokens = 1200
    candidates = sorted(ctx.hops, key=lambda p: scores.get(p, 0.0), reverse=True)
    for path in candidates:
        if len(ctx.files) >= max_files:
            break
        if ctx.total_tokens >= budget_tokens:
            break
        info = files[path]
        wanted = {
            q for q in info.symbols
            if q.split(".")[-1] in set(ctx.seeds)
            or (path, q) in seed_nodes
            or any((path, q) in edges.get(n, ()) or (path, q) in callers.get(n, ())
                   for n in seed_nodes)
        }
        if not wanted:
            if info.is_code:
                # Seed file with no matching symbol (e.g. a test module
                # that gets its runner from a fixture): contribute its
                # highest-PageRank symbols instead of nothing.
                ranked_all = sorted(
                    info.symbols,
                    key=lambda q: -rank.get((path, q), 0.0),
                )
                wanted = set(ranked_all[:3])
            else:
                wanted = set()
        ranked_syms = sorted(
            wanted,
            key=lambda q: (
                0 if q.split(".")[-1] in set(ctx.seeds) else 1,
                -rank.get((path, q), 0.0),
            ),
        )[:per_file_symbols]
        symbols = []
        tokens = 0
        for qualname in ranked_syms:
            start, end, text = info.snippet(qualname)
            frag_tokens = max(1, len(text) // 4)
            if tokens + frag_tokens > per_file_tokens:
                continue
            if ctx.total_tokens + tokens + frag_tokens > budget_tokens:
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
        if ctx.total_tokens + tokens > budget_tokens:
            continue
        if not symbols and tokens == 0:
            continue  # contributes nothing to the context; skip it
        ctx.files.append({
            "path": path, "score": round(scores.get(path, 0.0), 3),
            "hop": ctx.hops[path], "symbols": symbols, "tokens": tokens,
        })
        ctx.total_tokens += tokens
    return ctx
