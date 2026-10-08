"""Corpus loading + two-level BM25 retrieval over the committed KleidiAI corpus.

Ranking is doc-first: Okapi BM25 over whole docs (scaled by query-term
coverage) decides which doc canonically answers; chunk-level BM25 (with a
weighted heading field) orders passages within each doc. No embeddings, no
model download, no API key. The 2026-08-05 evals (evals/reports/report.md)
drove this design: the earlier token-overlap scorer's weakness categories all
reduced to raw term frequency rewarding "mentions the topic densely" over
"canonically answers" — addressed by BM25's IDF + length normalization — and
local static embeddings (potion-base-8M) were measured and REFUTED (28/48 vs
38/48 lexical; hybrid added a dependency for zero gain). The manifest is the
contract — only entries listed there, and not marked removed, are indexed.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    # The split() idiom is deliberate: one scannable line beats a 28-element
    # literal, and this list changes rarely (retriever A/Bs decide, not style).
    "a an and are as at be by do for how i in is it of on or the to what when where which why with you your".split()  # noqa: SIM905
)


@dataclass(frozen=True)
class DocChunk:
    """One heading-bounded section of a corpus doc, carrying its provenance."""

    doc_id: str
    url: str
    heading: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    """One ranked passage: provenance plus a query-focused snippet. The score
    is the doc-level relevance (what the cross-doc ordering means)."""

    doc_id: str
    url: str
    heading: str
    snippet: str
    score: float


def find_corpus_dir(start: Path | None = None) -> Path:
    """Locate the corpus directory.

    Resolution order: KLEIDIAI_CORPUS_DIR if set; else the nearest ancestor
    containing corpus/manifest.yaml (a repo checkout); else the copy staged
    inside the installed package at release time (distribution/
    prepare_corpus.py) — absent in a checkout, where the committed corpus is
    the single source of truth.
    """
    env = os.environ.get("KLEIDIAI_CORPUS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        candidate = parent / "corpus" / "manifest.yaml"
        if candidate.exists():
            return candidate.parent
    packaged = Path(__file__).parent / "_corpus"
    if (packaged / "manifest.yaml").exists():
        return packaged
    raise FileNotFoundError(
        "Could not locate corpus/manifest.yaml; set KLEIDIAI_CORPUS_DIR"
    )


def load_manifest(corpus_dir: Path) -> list[dict[str, Any]]:
    """Return the active source entries from corpus/manifest.yaml.

    The manifest is the indexing contract: only docs listed there, with full
    provenance and no `removed_at` marker, are ever indexed.
    """
    data = yaml.safe_load((corpus_dir / "manifest.yaml").read_text()) or {}
    return [s for s in (data.get("sources") or []) if not s.get("removed_at")]


def _chunk_markdown(text: str) -> list[tuple[str, str]]:
    """Split a markdown doc into (heading, body) sections at header boundaries."""
    heading = ""
    body: list[str] = []
    chunks: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            joined = "\n".join(body).strip()
            if heading or joined:
                chunks.append((heading, joined))
            heading = m.group(2).strip()
            body = []
        else:
            body.append(line)
    joined = "\n".join(body).strip()
    if heading or joined:
        chunks.append((heading, joined))
    return chunks


def load_chunks(corpus_dir: Path | None = None) -> list[DocChunk]:
    """Load every manifest-listed doc and split it into heading-bounded chunks.

    Chunks carry their doc id and source URL so search results always cite
    provenance.
    """
    corpus_dir = corpus_dir or find_corpus_dir()
    chunks: list[DocChunk] = []
    for src in load_manifest(corpus_dir):
        path = corpus_dir / src["path"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for heading, body in _chunk_markdown(text):
            chunks.append(
                DocChunk(
                    doc_id=src["id"],
                    url=src.get("url", ""),
                    heading=heading,
                    text=body,
                )
            )
    return chunks


def _tokens(s: str, stopwords: frozenset[str] = _STOPWORDS) -> list[str]:
    return [t for t in _TOKEN_RE.findall(s.lower()) if t not in stopwords]


def _snippet(text: str, terms: set[str], width: int = 280) -> str:
    lower = text.lower()
    pos = min((lower.find(t) for t in terms if lower.find(t) != -1), default=-1)
    if pos == -1:
        return text[:width].strip()
    start = max(0, pos - 60)
    end = start + width
    return ("…" if start > 0 else "") + text[start:end].strip() + ("…" if end < len(text) else "")


# MAX_PER_DOC keeps the result list useful to agents: the winning doc
# contributes its best passages, runner-up docs still appear.
_MAX_PER_DOC = 2


@dataclass(frozen=True)
class RetrievalConfig:
    """The retriever's settings. The server always uses the defaults; retriever
    A/Bs pass variants here instead of copying search().

    k1 and b are the standard Okapi BM25 defaults. Heading terms count
    heading_weight times in chunk stats, so a section titled for the query
    outranks a body mention (BM25F-lite). idf_coverage weights query-term
    coverage by doc-level IDF instead of counting distinct terms;
    section_rescue lets a doc score as its best section scored like a
    standalone doc. Both are off: the 2026-08-20 A/B refuted them.
    section_coverage measures coverage within a doc's best-covering section
    instead of the whole doc, so a long doc can't collect a query's words
    from unrelated sections. Off: its preregistered test on fresh questions
    was inconclusive (evals/build-guide/plan.md).
    """

    k1: float = 1.5
    b: float = 0.75
    heading_weight: int = 3
    stopwords: frozenset[str] = _STOPWORDS
    idf_coverage: bool = False
    section_rescue: bool = False
    section_coverage: bool = False


DEFAULT_CONFIG = RetrievalConfig()


@dataclass
class _Index:
    chunks: list[DocChunk]
    stopwords: frozenset[str]
    heading_weight: int
    # chunk level
    term_freqs: list[dict[str, int]]  # heading-weighted
    lengths: list[int]
    avg_length: float
    idf: dict[str, float]
    # doc level
    doc_term_freqs: dict[str, dict[str, int]]
    doc_lengths: dict[str, int]
    doc_avg_length: float
    doc_idf: dict[str, float]


_index: _Index | None = None


def _build_index(chunks: list[DocChunk], config: RetrievalConfig) -> _Index:
    term_freqs: list[dict[str, int]] = []
    lengths: list[int] = []
    df: dict[str, int] = {}
    doc_tf: dict[str, dict[str, int]] = {}
    for ch in chunks:
        tf: dict[str, int] = {}
        for t in _tokens(ch.text, config.stopwords):
            tf[t] = tf.get(t, 0) + 1
        for t in _tokens(ch.heading, config.stopwords):
            tf[t] = tf.get(t, 0) + config.heading_weight
        term_freqs.append(tf)
        lengths.append(sum(tf.values()))
        for t in tf:
            df[t] = df.get(t, 0) + 1
        dtf = doc_tf.setdefault(ch.doc_id, {})
        for t, n in tf.items():
            dtf[t] = dtf.get(t, 0) + n
    n = len(chunks)
    avg = (sum(lengths) / n) if n else 0.0
    idf = {t: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for t, d in df.items()}

    doc_lengths = {d: sum(tf.values()) for d, tf in doc_tf.items()}
    nd = len(doc_tf)
    doc_avg = (sum(doc_lengths.values()) / nd) if nd else 0.0
    doc_df: dict[str, int] = {}
    for tf in doc_tf.values():
        for t in tf:
            doc_df[t] = doc_df.get(t, 0) + 1
    doc_idf = {t: math.log((nd - d + 0.5) / (d + 0.5) + 1.0) for t, d in doc_df.items()}
    return _Index(
        chunks, config.stopwords, config.heading_weight, term_freqs, lengths, avg, idf,
        doc_tf, doc_lengths, doc_avg, doc_idf,
    )


def _bm25(
    matched: set[str], tf: dict[str, int], idf: dict[str, float], length: int, avg: float,
    config: RetrievalConfig,
) -> float:
    k1, b = config.k1, config.b
    norm = k1 * (1.0 - b + b * length / avg)
    return sum(idf[t] * (tf[t] * (k1 + 1.0)) / (tf[t] + norm) for t in matched)


def search(
    query: str, chunks: list[DocChunk], limit: int = 5, config: RetrievalConfig = DEFAULT_CONFIG
) -> list[SearchResult]:
    """Rank corpus passages for a query with two-level BM25.

    Doc-level BM25 (coverage-scaled) decides which docs canonically answer;
    chunk-level BM25 orders passages within each doc, capped at _MAX_PER_DOC
    so runner-up docs still surface. The reported score is the doc-level
    relevance. The index is built lazily and reused while the same chunk list
    and index-shaping settings are passed in.
    """
    global _index
    q = set(_tokens(query, config.stopwords))
    if not q:
        return []
    if (
        _index is None
        or _index.chunks is not chunks
        or (_index.stopwords, _index.heading_weight) != (config.stopwords, config.heading_weight)
    ):
        _index = _build_index(chunks, config)
    idx = _index
    idf_total = sum(idx.doc_idf.get(t, 0.0) for t in q)

    def coverage(matched: set[str]) -> float:
        if config.idf_coverage:
            return sum(idx.doc_idf[t] for t in matched) / idf_total if idf_total else 0.0
        return len(matched) / len(q)

    # Doc-level relevance: BM25 over the whole doc, scaled by query-term
    # coverage. Coverage keeps a doc that merely repeats one rare query term
    # from beating the doc that answers the query.
    best_section_cov: dict[str, float] = {}
    if config.section_coverage:
        for i, ch in enumerate(chunks):
            sec_matched = {t for t in q if t in idx.term_freqs[i]}
            if sec_matched:
                best_section_cov[ch.doc_id] = max(best_section_cov.get(ch.doc_id, 0.0), coverage(sec_matched))
    doc_score: dict[str, float] = {}
    for doc_id, dtf in idx.doc_term_freqs.items():
        matched = {t for t in q if t in dtf}
        if not matched:
            continue
        s = _bm25(matched, dtf, idx.doc_idf, idx.doc_lengths[doc_id], idx.doc_avg_length, config)
        cov = best_section_cov.get(doc_id, 0.0) if config.section_coverage else coverage(matched)
        doc_score[doc_id] = s * cov
    if config.section_rescue:
        for i, ch in enumerate(chunks):
            if ch.doc_id not in doc_score:
                continue
            matched = {t for t in q if t in idx.term_freqs[i]}
            if not matched:
                continue
            s = _bm25(matched, idx.term_freqs[i], idx.doc_idf, idx.lengths[i], idx.doc_avg_length, config)
            doc_score[ch.doc_id] = max(doc_score[ch.doc_id], s * coverage(matched))

    # Chunk-level relevance orders passages; doc-level relevance orders docs.
    # Heading-only chunks count toward doc stats but make useless passages.
    scored: list[tuple[float, float, int]] = []
    for i, ch in enumerate(chunks):
        if ch.doc_id not in doc_score or not ch.text.strip():
            continue
        tf = idx.term_freqs[i]
        matched = {t for t in q if t in tf}
        if not matched:
            continue
        chunk_s = _bm25(matched, tf, idx.idf, idx.lengths[i], idx.avg_length, config)
        scored.append((doc_score[ch.doc_id], chunk_s, i))
    scored.sort(reverse=True)

    # The reported score is the doc-level relevance (what the ordering means
    # across docs); passages within a doc are ordered by chunk relevance.
    results: list[SearchResult] = []
    per_doc: dict[str, int] = {}
    for d_s, _c_s, i in scored:
        ch = chunks[i]
        if per_doc.get(ch.doc_id, 0) >= _MAX_PER_DOC:
            continue
        per_doc[ch.doc_id] = per_doc.get(ch.doc_id, 0) + 1
        matched = {t for t in q if t in idx.term_freqs[i]}
        results.append(
            SearchResult(ch.doc_id, ch.url, ch.heading, _snippet(ch.text, matched), round(d_s, 3))
        )
        if len(results) >= limit:
            break
    return results
