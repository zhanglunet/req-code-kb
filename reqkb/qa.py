"""Ask the knowledge base: TF-IDF retrieval over settled pages.

No LLM call inside the MVP: retrieve the Top-5 passages with their
citations, assemble the prompt that *would* be fed to a model, and
print it. At the workshop the assembled prompt is pasted to a model
live -- one less thing that can fail on stage.
"""

from __future__ import annotations

import glob
import os
import re

from .retrieve import TfIdfIndex, tokenize
from .parse import FileInfo


def _sections(path: str) -> list[dict]:
    """Split a knowledge page into {heading, text} sections."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    parts = re.split(r"(?m)^## (.+)$", text)
    sections = [{"heading": "全文", "text": parts[0]}]
    for i in range(1, len(parts), 2):
        sections.append({
            "heading": parts[i].strip(),
            "text": parts[i + 1] if i + 1 < len(parts) else "",
        })
    return [{"heading": s["heading"], "text": s["text"], "page": path}
            for s in sections if s["text"].strip()]


def ask(kb_dir: str, question: str, top_k: int = 5) -> dict:
    pages = sorted(glob.glob(os.path.join(kb_dir, "requirements", "*.md")))
    docs: dict[str, FileInfo] = {}
    sections: list[dict] = []
    for page in pages:
        for sec in _sections(page):
            key = f"{page}#{sec['heading']}"
            docs[key] = FileInfo(key, sec["text"])
            sections.append({**sec, "key": key})
    index = TfIdfIndex(docs)
    query_vec = index.vector(tokenize(question))
    ranked = sorted(
        sections,
        key=lambda s: index.cosine(query_vec, s["key"]),
        reverse=True,
    )
    hits = [
        {
            "page": os.path.basename(s["page"]),
            "heading": s["heading"],
            "score": round(index.cosine(query_vec, s["key"]), 3),
            "excerpt": s["text"].strip()[:400],
        }
        for s in ranked[:top_k]
        if index.cosine(query_vec, s["key"]) > 0
    ]
    context = "\n\n".join(
        f"[{h['page']} §{h['heading']}]\n{h['excerpt']}" for h in hits
    )
    prompt = (
        "以下是与问题相关的知识库片段（带出处），请仅依据这些片段回答，"
        "片段里没有的就说不知道：\n\n"
        f"{context}\n\n问题：{question}\n"
    )
    return {"question": question, "hits": hits, "prompt": prompt}
