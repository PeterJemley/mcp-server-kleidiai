"""Assemble the build-guide test set from the agents' raw outputs (plan.md).

  inputs OUT_DIR  write the agents' input files outside the repo: every
                  eligible section (core writer), the build guides'
                  sections (extra writer) and the 7 documents (labeller)
  prepare         check raw/writer-core.jsonl and raw/writer-extra.jsonl,
                  then write raw/adjudicator_input.jsonl (questions only, in
                  a seeded shuffled order, under ids that don't reveal their
                  section) and raw/qid_map.tsv
  assemble        join the writers' and labeller's outputs into
                  questions.yaml

Nothing here edits a question or a label; it only checks shape and joins.

Run: ../../packages/server-py/.venv/bin/python build_set.py inputs DIR|prepare|assemble
"""

from __future__ import annotations

import json
import os
import random
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
sys.path.insert(0, os.path.join(HERE, "..", "heldout"))
import sections as heldout_sections  # noqa: E402

SHUFFLE_SEED = 20261009
BUILD_DOCS = ("llamacpp-build", "mlexamples-llamacpp-int4-patch")
DOC_IDS = {
    "kleidiai-readme", "llamacpp-build", "kleidiai-matmul-pack", "kleidiai-microkernel-names",
    "kleidiai-matmul-qsi4cx", "learnarm-llamacpp-sme2-integration", "mlexamples-llamacpp-int4-patch",
}


def eligible() -> list[dict]:
    return heldout_sections.eligible_sections()


def read_jsonl(name: str) -> list[dict]:
    with open(os.path.join(RAW, name)) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def inputs(out: str) -> None:
    sys.argv = ["sections.py", out]
    heldout_sections.main()
    extra = [s for s in eligible() if s["doc_id"] in BUILD_DOCS]
    with open(os.path.join(out, "extra_sections.json"), "w") as fh:
        json.dump([{"section_id": s["section_id"], "source": heldout_sections.LABELS[s["doc_id"]],
                    "heading": s["heading"], "text": s["text"]} for s in extra], fh, indent=1)
    print(f"{len(extra)} build-guide sections for the extra writer")


def all_questions() -> list[dict]:
    secs = eligible()
    doc = {s["section_id"]: s["doc_id"] for s in secs}
    core = read_jsonl("writer-core.jsonl")
    assert [r["section_id"] for r in core] == [s["section_id"] for s in secs], "core: every section, in order"
    extra = read_jsonl("writer-extra.jsonl")
    assert [r["section_id"] for r in extra] == [s["section_id"] for s in secs if s["doc_id"] in BUILD_DOCS], \
        "extra: every build-guide section, in order"
    out = []
    for r in core:
        assert (r["question"] is None) != (r["skip_reason"] is None), f"core {r['section_id']}: question xor skip_reason"
        if r["question"] is not None:
            out.append({"section_id": r["section_id"], "doc_id": doc[r["section_id"]], "part": "core",
                        "question": r["question"]})
    for r in extra:
        assert len(r["questions"]) == 2, f"extra {r['section_id']}: two slots"
        assert (None in r["questions"]) == (r["skip_reason"] is not None), f"extra {r['section_id']}: reason iff a null"
        for n, question in enumerate(r["questions"], 1):
            if question is not None:
                out.append({"section_id": r["section_id"], "doc_id": doc[r["section_id"]], "part": f"extra{n}",
                            "question": question})
    return out


def prepare() -> None:
    qs = all_questions()
    order = list(range(len(qs)))
    random.Random(SHUFFLE_SEED).shuffle(order)
    with open(os.path.join(RAW, "adjudicator_input.jsonl"), "w") as fh, \
            open(os.path.join(RAW, "qid_map.tsv"), "w") as mp:
        mp.write("qid\tsection_id\tpart\n")
        for pos, i in enumerate(order, 1):
            qid = f"q{pos:03d}"
            fh.write(json.dumps({"qid": qid, "question": qs[i]["question"]}) + "\n")
            mp.write(f"{qid}\t{qs[i]['section_id']}\t{qs[i]['part']}\n")
    parts = {p: sum(q["part"] == p for q in qs) for p in ("core", "extra1", "extra2")}
    print(f"{len(qs)} questions: {parts}")


def assemble() -> None:
    by_key = {(q["section_id"], q["part"]): q for q in all_questions()}
    with open(os.path.join(RAW, "qid_map.tsv")) as fh:
        qid_key = {r[0]: (r[1], r[2]) for r in (line.rstrip("\n").split("\t") for line in list(fh)[1:])}
    labels = read_jsonl("adjudicator.jsonl")
    assert [lab["qid"] for lab in read_jsonl("adjudicator_input.jsonl")] == [lab["qid"] for lab in labels], \
        "adjudicator output must cover every question, in order"
    out, unanswerable = [], []
    for lab in labels:
        unknown = set(lab["answering_doc_ids"]) - DOC_IDS
        assert not unknown, f"{lab['qid']}: unknown doc ids {unknown}"
        q = by_key[qid_key[lab["qid"]]]
        if not lab["answering_doc_ids"]:
            unanswerable.append(f"{q['section_id']}/{q['part']}")
            continue
        others = sorted(set(lab["answering_doc_ids"]) - {q["doc_id"]})
        out.append({
            "id": f"bg-{q['section_id'].replace('#', '-')}-{q['part']}",
            "question": q["question"],
            "expected_doc_ids": [q["doc_id"]] + others,
            "source_section": q["section_id"],
            "part": q["part"],
            "adjudicator_listed_source": q["doc_id"] in lab["answering_doc_ids"],
            "notes": lab.get("note", ""),
        })
    out.sort(key=lambda q: (q["source_section"], q["part"]))
    header = ("# Build-guide test set (evals/build-guide/plan.md). Generated by\n"
              "# build_set.py from raw/: do not edit by hand.\n")
    with open(os.path.join(HERE, "questions.yaml"), "w") as fh:
        fh.write(header)
        yaml.safe_dump({"version": 1, "excluded_unanswerable": unanswerable, "questions": out}, fh,
                       sort_keys=False, allow_unicode=True, width=100)
    print(f"{len(out)} questions; {len(unanswerable)} excluded as unanswerable by every doc")


if __name__ == "__main__":
    {"inputs": lambda: inputs(sys.argv[2]), "prepare": prepare, "assemble": assemble}[sys.argv[1]]()
