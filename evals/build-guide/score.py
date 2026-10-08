"""Measurements for build-guide/plan.md, run once on the frozen set.

Compares the shipped retriever (C0) with section coverage (C1) and, as the
rival explanation, stronger length normalization (C2). The retrieval call is
the promptfoo provider's: search the question, limit 5, top-1 doc. Prints
everything and writes score.out and results.tsv beside this file.

Run: ../../packages/server-py/.venv/bin/python score.py [QUESTIONS_YAML]
(a path scores another set in the same format and writes nothing, which is
how this script was tested on design data before the freeze)
"""

from __future__ import annotations

import importlib.util
import io
import os
import random
import statistics
import subprocess
import sys
import tempfile
from dataclasses import replace
from math import comb, sqrt

import yaml

from mcp_server_kleidiai import corpus as C

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "heldout"))
from sections import eligible_sections  # noqa: E402

PRE_CHANGE = "c494960"  # corpus.py before the section_coverage option existed
BUILD_DOCS = {"llamacpp-build", "mlexamples-llamacpp-int4-patch"}
CONFIGS = {
    "C0": C.DEFAULT_CONFIG,
    "C1": replace(C.DEFAULT_CONFIG, section_coverage=True),
    "C2": replace(C.DEFAULT_CONFIG, b=1.0),
}
SEED = 20261009


class Tee(io.StringIO):
    def write(self, s):
        sys.__stdout__.write(s)
        return super().write(s)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p, d = k / n, 1 + z * z / n
    c, h = p + z * z / (2 * n), z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def load(path: str) -> list[dict]:
    return yaml.safe_load(open(os.path.join(ARCHIVE, path)))["questions"]


def pre_change_module():
    src = subprocess.run(["git", "-C", ARCHIVE, "show", f"{PRE_CHANGE}:packages/server-py/src/mcp_server_kleidiai/corpus.py"],
                         capture_output=True, text=True, check=True).stdout
    path = os.path.join(tempfile.mkdtemp(), "corpus_pre_change.py")
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("corpus_pre_change", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["corpus_pre_change"] = mod
    spec.loader.exec_module(mod)
    return mod


def sign_flip_p(diffs: list[int]) -> float:
    """Exact two-sided p for the sum of per-section differences under random sign flips."""
    nz = [d for d in diffs if d]
    dist = {0: 1}
    for d in nz:
        nxt: dict[int, int] = {}
        for s, c in dist.items():
            nxt[s + d] = nxt.get(s + d, 0) + c
            nxt[s - d] = nxt.get(s - d, 0) + c
        dist = nxt
    t = abs(sum(nz))
    return sum(c for s, c in dist.items() if abs(s) >= t) / 2 ** len(nz)


def mcnemar_p(gain: int, loss: int) -> float:
    n, k = gain + loss, min(gain, loss)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def main() -> int:
    sys.stdout = Tee()
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "questions.yaml")
    qs = yaml.safe_load(open(path))["questions"]
    dev, v1 = load("evals/questions.yaml"), load("evals/heldout/questions.yaml")
    chunks = C.load_chunks()
    section_text = {s["section_id"]: s["text"] for s in eligible_sections()}
    core = [q for q in qs if q["part"] == "core"]
    target = [q for q in qs if q["expected_doc_ids"][0] in BUILD_DOCS]
    print(f"questions: {len(qs)} ({len(core)} core, one per section; {len(target)} from the two build guides)\n")

    def top(cfg, q, k=5):
        return [r.doc_id for r in C.search(q["question"], chunks, limit=k, config=cfg)]

    tops = {name: {q["id"]: top(cfg, q) for q in qs} for name, cfg in CONFIGS.items()}

    def top1(name, q):
        return (tops[name][q["id"]] or [""])[0]

    def right(name, q):
        return top1(name, q) in q["expected_doc_ids"]

    def confused(name, q):
        t = tops[name][q["id"]]
        return q["expected_doc_ids"][0] in BUILD_DOCS and bool(t) and t[0] in BUILD_DOCS and t[0] not in q["expected_doc_ids"]

    # --- Gates -------------------------------------------------------------------
    old = pre_change_module()

    def full(mod, query, **kw):
        return [(r.doc_id, r.url, r.heading, r.snippet, r.score) for r in mod.search(query, chunks, **kw)]
    queries = [q["question"] for q in qs + dev + v1]
    same = sum(full(C, x, limit=5) == full(old, x, limit=5) for x in queries)
    oracle = sum(top(CONFIGS["C0"], {"question": section_text[q["source_section"]]})[:1] == [q["expected_doc_ids"][0]]
                 for q in core)
    rand = statistics.mean(len(q["expected_doc_ids"]) / 7 for q in core)
    docs = sorted({d for q in core for d in q["expected_doc_ids"]})
    const_doc, const = max(((d, sum(d in q["expected_doc_ids"] for q in core)) for d in docs), key=lambda x: x[1])
    perm = list(range(len(core)))
    rng = random.Random(SEED)
    while any(i == p for i, p in enumerate(perm)):
        rng.shuffle(perm)
    shifted = sum(top1("C0", core[perm[i]]) in q["expected_doc_ids"] for i, q in enumerate(core))
    gates = [
        (same == len(queries), f"M option off = shipped retriever (full result lists, {len(queries)} queries): {same}/{len(queries)}"),
        (oracle >= 0.9 * len(core), f"A oracle on core (section text as query): {oracle}/{len(core)}; must be >= 90%"),
        (rand <= 0.30, f"B random-doc baseline on core: {rand:.1%}; must be <= 30%"),
        (shifted <= const + 0.10 * len(core),
         f"C shifted questions on core: {shifted}/{len(core)}; must be <= constant baseline + 10 points "
         f"({const}/{len(core)}, always '{const_doc}')"),
    ]
    print("VALIDITY GATES (any failure makes the measurement invalid)")
    for ok, what in gates:
        print(f"  {'ok' if ok else 'FAIL':4s} {what}")
    valid = all(ok for ok, _ in gates)
    print(f"  measurement {'VALID' if valid else 'INVALID'}\n")

    # --- Q1: does section coverage fix the confusion? -----------------------------
    gain = sum(right("C1", q) and not right("C0", q) for q in target)
    loss = sum(right("C0", q) and not right("C1", q) for q in target)
    per_section: dict[str, int] = {}
    for q in target:
        per_section[q["source_section"]] = per_section.get(q["source_section"], 0) + right("C1", q) - right("C0", q)
    p = sign_flip_p(list(per_section.values()))
    conf0, conf1 = sum(confused("C0", q) for q in target), sum(confused("C1", q) for q in target)
    if conf0 < 5:
        q1 = "INCONCLUSIVE: fewer than 5 confusions to fix"
    elif gain - loss > 0 and p < 0.05 and conf1 <= conf0 / 2:
        q1 = "SUPPORTED"
    elif gain - loss <= 0 or conf1 >= conf0:
        q1 = "REFUTED"
    else:
        q1 = "INCONCLUSIVE"
    print("Q1 build-guide questions, section coverage (C1) vs shipped (C0)")
    print(f"  accuracy C0 {sum(right('C0', q) for q in target)}/{len(target)}, C1 {sum(right('C1', q) for q in target)}/{len(target)}; "
          f"fixed {gain}, broken {loss}, net {gain - loss:+d}")
    print(f"  section-level sign-flip test (exact, two-sided): p = {p:.4f} "
          f"({sum(1 for d in per_section.values() if d)} sections changed)")
    print(f"  confusions between the two build guides: C0 {conf0}, C1 {conf1}")
    print(f"  verdict: {q1}\n")

    # --- Q2: adopt as the default? -------------------------------------------------
    c0_core, c1_core = sum(right("C0", q) for q in core), sum(right("C1", q) for q in core)
    adopt = valid and q1 == "SUPPORTED" and c1_core >= c0_core
    print("Q2 core set (one question per section, all documents)")
    lo0, hi0 = wilson(c0_core, len(core))
    lo1, hi1 = wilson(c1_core, len(core))
    print(f"  C0 {c0_core}/{len(core)} = {c0_core / len(core):.1%} ({lo0:.1%}-{hi0:.1%}); "
          f"C1 {c1_core}/{len(core)} = {c1_core / len(core):.1%} ({lo1:.1%}-{hi1:.1%}); net {c1_core - c0_core:+d}")
    print(f"  decision: {'ADOPT section coverage as the default' if adopt else 'KEEP the shipped retriever'}\n")

    # --- Secondary -------------------------------------------------------------------
    print("SECONDARY (no decision attached)")
    g2 = sum(right("C2", q) and not right("C0", q) for q in target)
    l2 = sum(right("C0", q) and not right("C2", q) for q in target)
    print(f"  S1 rival, length normalization b=1.0 (C2) on build-guide questions: fixed {g2}, broken {l2}, "
          f"confusions {sum(confused('C2', q) for q in target)}; on core {sum(right('C2', q) for q in core)}/{len(core)}")
    print(f"  S2 McNemar exact on build-guide questions, ignoring sections: p = {mcnemar_p(gain, loss):.4f}")
    for name in ("C0", "C1"):
        hit5 = sum(any(d in q["expected_doc_ids"] for d in tops[name][q["id"]]) for q in core)
        print(f"  S3 {name} correct doc anywhere in 5 results, core: {hit5}/{len(core)}")
    print("  S4 core accuracy by source doc (C0 -> C1):")
    for d in sorted({q["expected_doc_ids"][0] for q in core}):
        sub = [q for q in core if q["expected_doc_ids"][0] == d]
        print(f"     {d:38s} {sum(right('C0', q) for q in sub)}/{len(sub)} -> {sum(right('C1', q) for q in sub)}/{len(sub)}")
    v1_tokens = [set(C._tokens(x["question"])) for x in v1]

    def near_v1(q):
        t = set(C._tokens(q["question"]))
        return any(len(t & u) / len(t | u) >= 0.5 for u in v1_tokens if t | u)
    nd = [q for q in target if not near_v1(q)]
    nd_net = sum(right("C1", q) for q in nd) - sum(right("C0", q) for q in nd)
    print(f"  S5 near-duplicates of a design (v1) question among build-guide questions: {len(target) - len(nd)}; "
          f"net without them {nd_net:+d} of {len(nd)}")
    print("  S6 design data (already seen when choosing C1): ", end="")
    for name, cfg in CONFIGS.items():
        d = sum((top(cfg, x) or [""])[0] in x["expected_doc_ids"] for x in dev)
        v = sum((top(cfg, x) or [""])[0] in x["expected_doc_ids"] for x in v1)
        print(f"{name} dev {d}/{len(dev)} v1 {v}/{len(v1)}; ", end="")
    print()
    if len(sys.argv) > 1:
        return 0  # a test run on another set writes nothing

    with open(os.path.join(HERE, "results.tsv"), "w") as fh:
        fh.write("id\tpart\texpected\tC0_top1\tC1_top1\tC2_top1\tquestion\n")
        for q in qs:
            fh.write(f"{q['id']}\t{q['part']}\t{','.join(q['expected_doc_ids'])}\t"
                     + "\t".join(top1(n, q) for n in CONFIGS) + f"\t{q['question']}\n")
    with open(os.path.join(HERE, "score.out"), "w") as fh:
        fh.write(sys.stdout.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
