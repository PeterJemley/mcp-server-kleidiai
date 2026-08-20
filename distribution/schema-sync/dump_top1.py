"""Dump top-1 doc id for every eval question — Python side of the
cross-SDK retrieval-parity check. Output: "<question_id>\t<doc_id>" lines.
The two retrievers must agree on every line; a diff is a behavioral drift
between the implementations, not an eval score change.
"""

from __future__ import annotations

import os

import yaml

from mcp_server_kleidiai.corpus import load_chunks, search

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = os.path.join(HERE, "..", "..", "evals", "questions.yaml")


def main() -> None:
    """Print one tab-separated (question id, top-1 doc id) line per question."""
    with open(QUESTIONS) as fh:
        questions = yaml.safe_load(fh)["questions"]
    chunks = load_chunks()
    for q in questions:
        results = search(q["question"], chunks, limit=1)
        print(f"{q['id']}\t{results[0].doc_id if results else ''}")


if __name__ == "__main__":
    main()
