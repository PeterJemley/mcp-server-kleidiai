"""A/B for the 2026-08 doc-dilution regressions (see reports/report.md).

Measures top-1 accuracy over questions.yaml for combinations of three
candidate mechanisms, each isolated so the winner is chosen by measurement:

- rescue:    doc relevance = max(doc-level BM25, best section scored as if it
             were a standalone doc) — the fix sketched in where-to-begin.md.
- idfcov:    coverage weighted by doc-level IDF instead of raw distinct-term
             count, so generic query tokens can't buy coverage for long docs.
- stopwords: the standard NLTK English stopword list instead of the ad-hoc
             28-word list, so conversational question words ("that", "want",
             "can", "up") never enter scoring at all. Standard list, not
             eval-tuned picks.

Scoring is a parametrized copy of corpus.search's two-level BM25; the corpus
module stays untouched while experimenting.

Run: ../packages/server-py/.venv/bin/python retrieval/ab_dilution.py  (from evals/)
"""

from __future__ import annotations

import math
import os
import re
import sys

import yaml

from mcp_server_kleidiai.corpus import DocChunk, load_chunks

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN_COUNT = 30

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_K1 = 1.5
_B = 0.75
_HEADING_WEIGHT = 3

STOPWORDS_CURRENT = frozenset(
    "a an and are as at be by do for how i in is it of on or the to what when where which why with you your".split()
)

# NLTK English stopword list, tokenized the same way corpus.py tokenizes
# (contractions split at the apostrophe, so their fragments appear too).
STOPWORDS_NLTK = frozenset("""
i me my myself we our ours ourselves you your yours yourself yourselves he him
his himself she her hers herself it its itself they them their theirs
themselves what which who whom this that these those am is are was were be
been being have has had having do does did doing a an the and but if or
because as until while of at by for with about against between into through
during before after above below to from up down in out on off over under
again further then once here there when where why how all any both each few
more most other some such no nor not only own same so than too very s t can
will just don should now d ll m o re ve y ain aren couldn didn doesn hadn
hasn haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn
""".split())


def tokens(s: str, stop: frozenset[str]) -> list[str]:
    """Tokenize with the given stopword list (mirrors corpus._tokens)."""
    return [t for t in _TOKEN_RE.findall(s.lower()) if t not in stop]


def bm25(matched, tf, idf, length, avg):
    """Okapi BM25 term sum (same formula and constants as corpus.py)."""
    norm = _K1 * (1.0 - _B + _B * length / avg)
    return sum(idf[t] * (tf[t] * (_K1 + 1.0)) / (tf[t] + norm) for t in matched)


def build(chunks: list[DocChunk], stop: frozenset[str]):
    """Build chunk- and doc-level term statistics for one stopword list."""
    term_freqs, lengths, doc_tf = [], [], {}
    for ch in chunks:
        tf: dict[str, int] = {}
        for t in tokens(ch.text, stop):
            tf[t] = tf.get(t, 0) + 1
        for t in tokens(ch.heading, stop):
            tf[t] = tf.get(t, 0) + _HEADING_WEIGHT
        term_freqs.append(tf)
        lengths.append(sum(tf.values()))
        dtf = doc_tf.setdefault(ch.doc_id, {})
        for t, n in tf.items():
            dtf[t] = dtf.get(t, 0) + n
    doc_lengths = {d: sum(tf.values()) for d, tf in doc_tf.items()}
    nd = len(doc_tf)
    doc_avg = sum(doc_lengths.values()) / nd
    doc_df: dict[str, int] = {}
    for tf in doc_tf.values():
        for t in tf:
            doc_df[t] = doc_df.get(t, 0) + 1
    doc_idf = {t: math.log((nd - d + 0.5) / (d + 0.5) + 1.0) for t, d in doc_df.items()}
    return term_freqs, lengths, doc_tf, doc_lengths, doc_avg, doc_idf


def top1(query, chunks, index, stop, idfcov, rescue):
    """Return the top-1 doc id for a query under the given config."""
    term_freqs, lengths, doc_tf, doc_lengths, doc_avg, doc_idf = index
    q = set(tokens(query, stop))
    if not q:
        return ""
    idf_total = sum(doc_idf.get(t, 0.0) for t in q)

    def coverage(matched):
        """Query-term coverage: IDF-weighted or raw distinct-term fraction."""
        if idfcov:
            return (sum(doc_idf[t] for t in matched) / idf_total) if idf_total else 0.0
        return len(matched) / len(q)

    doc_score: dict[str, float] = {}
    for doc_id, dtf in doc_tf.items():
        matched = {t for t in q if t in dtf}
        if matched:
            s = bm25(matched, dtf, doc_idf, doc_lengths[doc_id], doc_avg)
            doc_score[doc_id] = s * coverage(matched)
    if rescue:
        for i, ch in enumerate(chunks):
            if ch.doc_id not in doc_score:
                continue
            matched = {t for t in q if t in term_freqs[i]}
            if not matched:
                continue
            s = bm25(matched, term_freqs[i], doc_idf, lengths[i], doc_avg)
            s *= coverage(matched)
            if s > doc_score[ch.doc_id]:
                doc_score[ch.doc_id] = s
    return max(doc_score, key=doc_score.get) if doc_score else ""


def main() -> int:
    """Score every (stopwords, idfcov, rescue) config; print deltas vs baseline."""
    with open(os.path.join(HERE, "..", "questions.yaml")) as fh:
        questions = yaml.safe_load(fh)["questions"]
    chunks = load_chunks()
    configs = [
        (name, stop, idfcov, rescue)
        for name, stop in (("cur-stop", STOPWORDS_CURRENT), ("nltk-stop", STOPWORDS_NLTK))
        for idfcov in (False, True)
        for rescue in (False, True)
    ]
    baseline_fails = None
    for name, stop, idfcov, rescue in configs:
        index = build(chunks, stop)
        passed = frozen = 0
        fails = []
        for i, qq in enumerate(questions):
            got = top1(qq["question"], chunks, index, stop, idfcov, rescue)
            if got in qq["expected_doc_ids"]:
                passed += 1
                frozen += i < FROZEN_COUNT
            else:
                fails.append(qq["id"])
        label = f"{name} idfcov={int(idfcov)} rescue={int(rescue)}"
        print(f"{label:38s} overall={passed}/{len(questions)} frozen={frozen}/{FROZEN_COUNT}")
        if baseline_fails is None:
            baseline_fails = set(fails)
        else:
            new = sorted(set(fails) - baseline_fails)
            fixed = sorted(baseline_fails - set(fails))
            if fixed:
                print(f"{'':38s}   fixed: {', '.join(fixed)}")
            if new:
                print(f"{'':38s}   broke: {', '.join(new)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
