"""Retriever A/B over named RetrievalConfig variants of corpus.search.

Re-expresses the 2026-08-20 dilution A/B (plan: config-seam.md): each candidate
is a configuration of the one search() the server runs, not a copy of it. Every
configuration's top-1 doc per question is written to ab_configs.tsv, so a
comparison's per-question record is committed with it.

Run: ../packages/server-py/.venv/bin/python retrieval/ab_configs.py  (from evals/)
"""

from __future__ import annotations

import os
from dataclasses import replace

import yaml

from mcp_server_kleidiai.corpus import DEFAULT_CONFIG, DocChunk, RetrievalConfig, load_chunks, search

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN_COUNT = 30

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

CONFIGS: dict[str, RetrievalConfig] = {
    f"{name} idfcov={int(idf)} rescue={int(rescue)}": replace(
        DEFAULT_CONFIG, stopwords=stop, idf_coverage=idf, section_rescue=rescue
    )
    for name, stop in (("cur-stop", DEFAULT_CONFIG.stopwords), ("nltk-stop", STOPWORDS_NLTK))
    for idf in (False, True)
    for rescue in (False, True)
}


def top1(question: str, chunks: list[DocChunk], config: RetrievalConfig) -> str:
    """The doc the server would rank first under this configuration."""
    results = search(question, chunks, config=config)
    return results[0].doc_id if results else ""


def main() -> int:
    """Score every configuration, write the per-question record, print deltas."""
    with open(os.path.join(HERE, "..", "questions.yaml")) as fh:
        questions = yaml.safe_load(fh)["questions"]
    chunks = load_chunks()
    got = {label: [top1(q["question"], chunks, c) for q in questions] for label, c in CONFIGS.items()}

    with open(os.path.join(HERE, "ab_configs.tsv"), "w") as fh:
        fh.write("\t".join(["id", *CONFIGS]) + "\n")
        for i, q in enumerate(questions):
            fh.write("\t".join([q["id"], *(got[label][i] for label in CONFIGS)]) + "\n")

    baseline_fails: set[str] | None = None
    for label in CONFIGS:
        hits = [doc in q["expected_doc_ids"] for doc, q in zip(got[label], questions)]
        fails = {q["id"] for hit, q in zip(hits, questions) if not hit}
        print(f"{label:38s} overall={sum(hits)}/{len(questions)} frozen={sum(hits[:FROZEN_COUNT])}/{FROZEN_COUNT}")
        if baseline_fails is None:
            baseline_fails = fails
            continue
        for word, ids in (("fixed", baseline_fails - fails), ("broke", fails - baseline_fails)):
            if ids:
                print(f"{'':38s}   {word}: {', '.join(sorted(ids))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
