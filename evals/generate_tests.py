"""Generate Promptfoo test cases from questions.yaml (single source of truth).

Each question becomes a test asserting the provider's top-1 doc id is one of the
question's expected_doc_ids. HARD questions are still asserted normally — a
failure is the signal, per the evals-don't-lie rule.
"""

from __future__ import annotations

import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


def generate_tests():
    """Promptfoo hook: expand questions.yaml into one test case per question."""
    with open(os.path.join(HERE, "questions.yaml")) as fh:
        data = yaml.safe_load(fh)
    tests = []
    for q in data["questions"]:
        tests.append(
            {
                "description": q["id"],
                "vars": {
                    "question": q["question"],
                    # Joined, not a list: promptfoo expands array vars into one
                    # test per element, which breaks multi-doc ground truth.
                    "expected": ",".join(q["expected_doc_ids"]),
                    "hard": str(q["id"]).startswith("hard-"),
                },
                "assert": [
                    {
                        "type": "javascript",
                        "value": "context.vars.expected.split(',').includes(String(output).trim())",
                    }
                ],
            }
        )
    return tests
