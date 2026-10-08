"""Score the held-out set once, as plan.md specifies: the primary measure and
its decision, the validity gates, and the secondary measures.

The retrieval call is the promptfoo provider's (mcp_provider.py): search the
question, limit 5, top-1 doc. Prints everything and writes score.out and a
per-question results.tsv beside this file.

Run: ../../packages/server-py/.venv/bin/python score.py [QUESTIONS_YAML]
(defaults to questions.yaml here; any set in the same format can be scored,
which is how this script was tested on the development set before freezing)
"""

from __future__ import annotations

import io
import os
import random
import re
import statistics
import sys
from math import sqrt

import yaml

from mcp_server_kleidiai.corpus import _tokens, find_corpus_dir, load_chunks, load_manifest, search

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sections import eligible_sections  # noqa: E402

DEV_SCORE = (41, 51)
THRESHOLD = 0.70
N_DOCS = 7
DERANGE_SEED = 20261008


class Tee(io.StringIO):
    def write(self, s):
        sys.__stdout__.write(s)
        return super().write(s)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p, d = k / n, 1 + z * z / n
    c, h = p + z * z / (2 * n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def pct(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.1%} (95% Wilson {lo:.1%}-{hi:.1%})"


def top_docs(query: str, chunks) -> list[str]:
    return [r.doc_id for r in search(query, chunks, limit=5)]


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", s.lower())


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "questions.yaml")
    sys.stdout = Tee()
    qs = yaml.safe_load(open(path))["questions"]
    dev = yaml.safe_load(open(os.path.join(HERE, "..", "questions.yaml")))["questions"]
    chunks = load_chunks()
    corpus = find_corpus_dir()
    doc_text = {s["id"]: (corpus / s["path"]).read_text(encoding="utf-8") for s in load_manifest(corpus)}
    section_text = {s["section_id"]: s["text"] for s in eligible_sections()}
    n = len(qs)
    print(f"questions: {os.path.relpath(path, HERE)} ({n}); chunks: {len(chunks)}\n")

    tops = [top_docs(q["question"], chunks) for q in qs]
    top1 = [t[0] if t else "" for t in tops]
    hit = [t1 in q["expected_doc_ids"] for t1, q in zip(top1, qs)]
    k = sum(hit)

    # --- Primary ---------------------------------------------------------------
    lo, hi = wilson(k, n)
    if lo >= THRESHOLD:
        verdict = "SUPPORTED: the development score generalizes (held-out within 10 points of 80%)"
    elif hi < THRESHOLD:
        verdict = "REFUTED: the development score overstates held-out accuracy by more than 10 points"
    else:
        verdict = "INCONCLUSIVE: the interval straddles 70%"
    print("PRIMARY top-1 doc accuracy:", pct(k, n))
    print(f"  development set for reference: {pct(*DEV_SCORE)}")
    print(f"  decision ({THRESHOLD:.0%} threshold on the Wilson interval): {verdict}\n")

    # --- Validity gates ----------------------------------------------------------
    with_src = [q for q in qs if q.get("source_section") in section_text]
    oracle = sum(top_docs(section_text[q["source_section"]], chunks)[:1] == [q["expected_doc_ids"][0]] for q in with_src)
    rand = statistics.mean(len(q["expected_doc_ids"]) / N_DOCS for q in qs)
    const_doc, const = max(((d, sum(d in q["expected_doc_ids"] for q in qs)) for d in doc_text), key=lambda x: x[1])
    perm = list(range(n))
    rng = random.Random(DERANGE_SEED)
    while any(i == p for i, p in enumerate(perm)):
        rng.shuffle(perm)
    shifted = sum(top1[perm[i]] in q["expected_doc_ids"] for i, q in enumerate(qs))
    gates = [
        (len(with_src) > 0 and oracle / len(with_src) >= 0.90,
         f"A oracle (section text as query, top-1 = source doc): {oracle}/{len(with_src)}; must be >= 90%"),
        (rand <= 0.30, f"B random-doc baseline (expected accuracy): {rand:.1%}; must be <= 30%"),
        (shifted / n <= const / n + 0.10,
         f"C shifted questions (each scored with another question's top-1): {shifted}/{n} = {shifted / n:.1%}; "
         f"must be <= constant baseline + 10 points ({const}/{n} = {const / n:.1%}, always '{const_doc}')"),
    ]
    print("VALIDITY GATES (any failure makes the measurement invalid, whatever the score)")
    for ok, what in gates:
        print(f"  {'ok' if ok else 'FAIL':4s} {what}")
    print(f"  measurement {'VALID' if all(ok for ok, _ in gates) else 'INVALID'}\n")

    # --- Secondary -------------------------------------------------------------
    print("SECONDARY (no decision attached)")
    hit5 = sum(any(d in q["expected_doc_ids"] for d in t) for t, q in zip(tops, qs))
    print("  S1 expected doc anywhere in the 5 results:", pct(hit5, n))
    strict = sum(t1 == q["expected_doc_ids"][0] for t1, q in zip(top1, qs))
    print("  S2 strict ground truth (source doc only):", pct(strict, n))
    dev_tokens = [set(_tokens(d["question"])) for d in dev]
    dup = [max((len(set(_tokens(q["question"])) & t) / len(set(_tokens(q["question"])) | t) for t in dev_tokens),
               default=0) >= 0.5 for q in qs]
    nd = [h for h, d in zip(hit, dup) if not d]
    print(f"  S3 near-duplicates of a development question (token Jaccard >= 0.5): {sum(dup)}; "
          f"without them: {pct(sum(nd), len(nd)) if nd else 'n/a'}")
    listed = [h for h, q in zip(hit, qs) if q.get("adjudicator_listed_source", True)]
    print(f"  S4 questions where the adjudicator did not list the source doc: {n - len(listed)}; "
          f"without them: {pct(sum(listed), len(listed)) if listed else 'n/a'}")
    multi = sum(len(q["expected_doc_ids"]) > 1 for q in qs)
    print(f"     questions with more than one correct doc: {multi}/{n}")
    print("  S5 by source doc:")
    per = {}
    for h, q in zip(hit, qs):
        per.setdefault(q["expected_doc_ids"][0], []).append(h)
    for d, hs in sorted(per.items()):
        print(f"     {d:38s} {sum(hs)}/{len(hs)}")
    print(f"     doc-balanced (mean of per-doc accuracy): {statistics.mean(sum(h) / len(h) for h in per.values()):.1%}")

    def overlap(question, doc):
        t = set(_tokens(question))
        body = set(_tokens(doc_text[doc]))
        return len(t & body) / len(t) if t else 0.0
    print(f"  S6 share of question words found in the first correct doc: held-out "
          f"{statistics.mean(overlap(q['question'], q['expected_doc_ids'][0]) for q in qs):.2f}, development "
          f"{statistics.mean(overlap(d['question'], d['expected_doc_ids'][0]) for d in dev):.2f}")
    copied = 0
    for q in with_src:
        w, sec = words(q["question"]), " ".join(words(section_text[q["source_section"]]))
        copied += any(" ".join(w[i:i + 4]) in sec for i in range(len(w) - 3))
    print(f"     questions repeating 4+ consecutive words of their section: {copied}/{len(with_src)}")

    if len(sys.argv) > 1:
        return 0  # a test run on another set writes nothing
    with open(os.path.join(HERE, "results.tsv"), "w") as fh:
        fh.write("id\tcorrect\ttop1\texpected\ttop5_docs\tquestion\n")
        for q, h, t in zip(qs, hit, tops):
            fh.write(f"{q['id']}\t{int(h)}\t{t[0] if t else ''}\t{','.join(q['expected_doc_ids'])}\t"
                     f"{','.join(t)}\t{q['question']}\n")
    with open(os.path.join(HERE, "score.out"), "w") as fh:
        fh.write(sys.stdout.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
