"""Fast retrieval check for development iteration.

Scores top-1 accuracy over questions.yaml by calling corpus.search directly —
same metric as the promptfoo harness, without its startup cost. Use while
developing the retriever; the committed record is still the promptfoo run
(reports/report.json + report.md).

Run: ../packages/server-py/.venv/bin/python dev_check.py [-v]
"""

from __future__ import annotations

import os
import sys

import yaml

from mcp_server_kleidiai.corpus import load_chunks, search

HERE = os.path.dirname(os.path.abspath(__file__))

# The first 30 question ids form the frozen pre-swap baseline subset
# (2026-07-14 set with † resolutions); batch 3 follows.
FROZEN_COUNT = 30


def main() -> int:
    """Score top-1 doc accuracy over questions.yaml; -v lists failures."""
    verbose = "-v" in sys.argv
    with open(os.path.join(HERE, "questions.yaml")) as fh:
        questions = yaml.safe_load(fh)["questions"]
    chunks = load_chunks()

    passed_all = passed_frozen = 0
    failures = []
    for i, q in enumerate(questions):
        results = search(q["question"], chunks, limit=5)
        got = results[0].doc_id if results else ""
        ok = got in q["expected_doc_ids"]
        if ok:
            passed_all += 1
            if i < FROZEN_COUNT:
                passed_frozen += 1
        else:
            failures.append((q["id"], q["expected_doc_ids"], got))

    print(f"overall:  {passed_all}/{len(questions)}")
    print(f"frozen30: {passed_frozen}/{FROZEN_COUNT}")
    if verbose:
        for qid, exp, got in failures:
            print(f"  FAIL {qid}: want {'|'.join(exp)}, got {got}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
