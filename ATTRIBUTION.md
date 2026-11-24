# ATTRIBUTION

This project (MIT) stands on the following work. What was borrowed
and what was not is stated plainly for each item.

## Aider repo map — algorithm idea only (Apache-2.0)

- Source: `aider-ai/aider`, `aider/repomap.py` (27,306 bytes, Apache-2.0).
- Borrowed: the pipeline shape — extract symbols → build a call
  graph → PageRank → cut by token budget — and the idea of seeding
  the ranking from identifiers (Aider seeds from the files in the
  current conversation; req-code-kb seeds from the identifiers in
  the requirement document).
- **No code copied.** `reqkb/` is a from-scratch reimplementation
  on the standard-library `ast` module, so the MVP has zero
  dependencies and no long-term dependency on a project whose
  main-branch commits slowed after 2026-05-22.

## github/spec-kit — spec template structure (MIT)

- Source: `github/spec-kit` (MIT).
- Borrowed: the shape of a requirement document (title / background /
  acceptance criteria). `examples/click-req-*.md` follow that shape.

## deepwiki-open — product shape only (MIT)

- Source: `AsyncFuncAI/deepwiki-open` (MIT).
- Borrowed: the presentation shape — wiki page + Mermaid diagram +
  RAG-style Q&A. No code copied (it is a Next.js app; this MVP is a
  Python CLI + Markdown pages).

## RepoGraph — k-hop retrieval strategy (ICLR 2025 paper)

- Paper: RepoGraph, ICLR 2025. Borrowed: k-hop ego-graph retrieval
  (+32.8% reported in the paper) as the expansion rule — 1-hop
  neighbours always in, 2-hop filtered by PageRank. No code copied.

## Evidence numbers (cited, not copied)

- SWE-Explore (2026): context efficiency vs. downstream repair
  success, Pearson r = +0.950. arXiv:2606.07297. A correlation across
  explorers, not a per-repair guarantee.
- Microsoft FastContext (2026): integrating the explorer subagent
  improves end-to-end resolution rates by up to 5.5% while reducing
  main-agent token consumption by up to 60%. arXiv:2606.14066.
  "Up to" is the paper's wording; token counts cover the main-agent
  trajectory only.

## TF-IDF retrieval — prior internal work

- The zero-dependency TF-IDF retrieval follows the same approach as
  the FDE Q&A bot built earlier in this workspace.

## Example repository: pallets/click (BSD-3-Clause)

- The worked example uses pallets/click (BSD-3-Clause). The
  requirement documents in `examples/` paraphrase the public PR
  descriptions of click #3896 and #3878 (author: kdeldycke) with
  changed-file lists hidden for the blind test. The settled
  knowledge pages link back to the click repository at the exact
  commit they were built from.

## Explicitly NOT used

- SocratiCode (AGPL-3.0): ideas only, never copied, never a
  dependency — otherwise it would contaminate this project's MIT
  license.
- Sweep (current version BSL): ideas only, no current code copied.
