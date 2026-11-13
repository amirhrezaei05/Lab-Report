
"""Lightweight, dependency-free lexical retrieval over the bundled lab-medicine KBs.

The source markdown is indexed lazily and cached per process. This is deliberately
transparent: every returned passage carries a stable source ID and relative path.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import hashlib
import math
import re
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parents[4]
KB_ROOT = PROJECT_ROOT / "knowledgeBaseForLabAI"
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{1,}|[0-9]+|[\u0600-\u06ff]{2,}", re.UNICODE)
SKIP_NAMES = {
    "copyright.md", "notice.md", "dedication.md", "acknowledgments.md",
    "authors.md", "editor.md", "log.md", "preface.md", "index.md",
    "financial-management.md", "node-20.md",
}


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _source_title(path: Path) -> str:
    # Book title is the first directory under the KB root.
    try:
        return path.relative_to(KB_ROOT).parts[0]
    except Exception:
        return path.parent.name


@lru_cache(maxsize=1)
def _load_chunks() -> tuple[dict, ...]:
    chunks: list[dict] = []
    if not KB_ROOT.exists():
        return tuple()
    for path in sorted(KB_ROOT.rglob("*.md")):
        if path.name.lower() in SKIP_NAMES:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Keep markdown headings in their associated paragraph for context.
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        buffer = ""
        for paragraph in paragraphs:
            if len(buffer) + len(paragraph) > 1500 and buffer:
                _append_chunk(chunks, path, buffer)
                buffer = ""
            buffer = (buffer + "\n\n" + paragraph).strip()
        if buffer:
            _append_chunk(chunks, path, buffer)
    return tuple(chunks)


def _append_chunk(chunks: list[dict], path: Path, text: str) -> None:
    terms = _tokens(text)
    if len(terms) < 12:
        return
    rel = path.relative_to(PROJECT_ROOT).as_posix()
    digest = hashlib.sha1((rel + text[:300]).encode("utf-8")).hexdigest()[:12]
    chunks.append({
        "source_id": f"kb_{digest}",
        "title": _source_title(path),
        "source_type": "textbook_reference",
        "path": rel,
        "text": text[:1800],
        "terms": Counter(terms),
        "length": len(terms),
    })


def retrieve_evidence(query: str, top_k: int = 7) -> list[dict]:
    docs = _load_chunks()
    qterms = set(_tokens(query))
    if not docs or not qterms:
        return []
    df = Counter()
    for doc in docs:
        df.update(set(doc["terms"]) & qterms)
    n = len(docs)
    scored = []
    for doc in docs:
        score = 0.0
        for term in qterms:
            tf = doc["terms"].get(term, 0)
            if tf:
                idf = math.log(1 + (n - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
                score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * doc["length"] / 220))
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    per_file = Counter()
    for score, doc in scored:
        # Prefer distinct sections so the model sees a range of relevant material.
        if per_file[doc["path"]] >= 1:
            continue
        per_file[doc["path"]] += 1
        results.append({
            "source_id": doc["source_id"],
            "title": doc["title"],
            "source_type": doc["source_type"],
            "path": doc["path"],
            "relevance_score": round(score, 4),
            "excerpt": doc["text"][:1000],
        })
        if len(results) >= top_k:
            break
    return results


def knowledge_base_status() -> dict:
    docs = _load_chunks()
    sources = sorted({d["title"] for d in docs})
    return {
        "available": bool(docs),
        "chunk_count": len(docs),
        "source_collections": sources,
        "retrieval_method": "BM25-style lexical ranking over Markdown sections",
    }
