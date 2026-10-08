"""Eligible corpus sections for the held-out set, and the agents' input files.

Every heading-bounded section (the server's own chunking) whose body has at
least MIN_WORDS words is eligible; the held-out set takes one question from
each, so no sampling choice is involved (plan.md).

Run: ../../packages/server-py/.venv/bin/python sections.py OUT_DIR
Writes sections.tsv beside this file (committed: ids and text hashes), and
OUT_DIR/sections.json (writer input) and OUT_DIR/corpus_docs.json
(adjudicator input), kept outside the repo so the agents see nothing else.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

from mcp_server_kleidiai.corpus import find_corpus_dir, load_chunks, load_manifest

MIN_WORDS = 30
HERE = os.path.dirname(os.path.abspath(__file__))

# Short neutral names for context; the manifest descriptions are keyword lists.
LABELS = {
    "kleidiai-readme": "KleidiAI README",
    "llamacpp-build": "llama.cpp build guide",
    "kleidiai-matmul-pack": "KleidiAI matmul packing guide",
    "kleidiai-microkernel-names": "KleidiAI micro-kernel naming guide",
    "kleidiai-matmul-qsi4cx": "KleidiAI int4 matmul guide",
    "learnarm-llamacpp-sme2-integration": "Arm learning path: KleidiAI inside llama.cpp",
    "mlexamples-llamacpp-int4-patch": "Arm ML examples: KleidiAI int4 patch for llama.cpp",
}


def eligible_sections() -> list[dict]:
    sections, index = [], {}
    for c in load_chunks():
        i = index[c.doc_id] = index.get(c.doc_id, -1) + 1
        if len(c.text.split()) >= MIN_WORDS:
            sections.append({"section_id": f"{c.doc_id}#{i:02d}", "doc_id": c.doc_id,
                             "heading": c.heading, "text": c.text})
    return sections


def main() -> int:
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    sections = eligible_sections()
    with open(os.path.join(HERE, "sections.tsv"), "w") as fh:
        fh.write("section_id\tdoc_id\twords\tsha256\theading\n")
        for s in sections:
            digest = hashlib.sha256(s["text"].encode()).hexdigest()
            fh.write(f"{s['section_id']}\t{s['doc_id']}\t{len(s['text'].split())}\t{digest}\t{s['heading']}\n")
    with open(os.path.join(out, "sections.json"), "w") as fh:
        json.dump([{"section_id": s["section_id"], "source": LABELS[s["doc_id"]], "heading": s["heading"],
                    "text": s["text"]} for s in sections], fh, indent=1)
    corpus = find_corpus_dir()
    docs = [{"doc_id": src["id"], "title": LABELS[src["id"]],
             "text": (corpus / src["path"]).read_text(encoding="utf-8")} for src in load_manifest(corpus)]
    with open(os.path.join(out, "corpus_docs.json"), "w") as fh:
        json.dump(docs, fh, indent=1)
    print(f"{len(sections)} eligible sections (>= {MIN_WORDS} words) from {len(docs)} docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
