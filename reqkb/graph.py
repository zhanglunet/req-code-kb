"""Call graph + PageRank ranking.

The Aider repo-map idea in miniature: symbols are nodes, calls are
edges, and PageRank says which symbols matter most -- like academic
citations, the more a function is called, the more important it is.
Reimplemented here in ~60 lines; no code copied from Aider.
"""

from __future__ import annotations

from .parse import FileInfo

Node = tuple[str, str]  # (file path, qualified symbol name)


def build_graph(files: dict[str, FileInfo]) -> tuple[set[Node], dict[Node, set[Node]]]:
    """Resolve calls to definitions by simple name.

    Same-file definitions win; otherwise every same-named definition
    in the repo is linked (PageRank tolerates the noise, and the
    retrieval score -- not the graph -- does the precise localisation).
    """
    by_simple: dict[str, list[Node]] = {}
    nodes: set[Node] = set()
    for path, info in files.items():
        for qualname in info.symbols:
            node = (path, qualname)
            nodes.add(node)
            by_simple.setdefault(qualname.split(".")[-1], []).append(node)

    edges: dict[Node, set[Node]] = {n: set() for n in nodes}
    for path, info in files.items():
        for caller, calls in info.calls.items():
            src = (path, caller)
            if src not in nodes:
                src = (path, "<module>")
                if src not in nodes:
                    continue
            for callee_name, _lineno in calls:
                targets = by_simple.get(callee_name, [])
                same_file = [t for t in targets if t[0] == path]
                for tgt in same_file or targets:
                    if tgt != src:
                        edges[src].add(tgt)
    return nodes, edges


def pagerank(nodes: set[Node], edges: dict[Node, set[Node]],
             damping: float = 0.85, iters: int = 100,
             tol: float = 1e-6) -> dict[Node, float]:
    """Classic power-iteration PageRank with dangling-node redistribution."""
    n = len(nodes)
    if n == 0:
        return {}
    rank = {node: 1.0 / n for node in nodes}
    out_degree = {node: len(edges.get(node, ())) for node in nodes}
    incoming: dict[Node, list[Node]] = {node: [] for node in nodes}
    for src, dsts in edges.items():
        for dst in dsts:
            incoming[dst].append(src)
    for _ in range(iters):
        dangling = sum(rank[node] for node in nodes if out_degree[node] == 0)
        new_rank = {}
        delta = 0.0
        for node in nodes:
            value = (1.0 - damping) / n + damping * dangling / n
            value += damping * sum(
                rank[src] / out_degree[src] for src in incoming[node]
            )
            new_rank[node] = value
            delta = max(delta, abs(value - rank[node]))
        rank = new_rank
        if delta < tol:
            break
    return rank


def file_scores(files: dict[str, FileInfo],
                rank: dict[Node, float]) -> dict[str, float]:
    """Aggregate symbol PageRank into a per-file score (sum)."""
    scores: dict[str, float] = {path: 0.0 for path in files}
    for (path, _qualname), value in rank.items():
        scores[path] += value
    return scores
