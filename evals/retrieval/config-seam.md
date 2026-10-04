# Preregistration: a configuration seam for the retriever

- **Written:** 2026-10-04, before any implementation or run.
- **Commit:** the commit that adds this file.
- **Status:** confirmatory.

## Why

A study of this repository's history (2026-10-04) found that alternative
retrievers have been built by copying or patching `corpus.search`: three of
the six cases where an alternative was tried. One of those cases lost its
code and per-question results for good (the 2026-08-05 semantic and
chunk-level candidates). The conjecture is that a single configurable
`search()`, exposing the settings past comparisons actually varied, removes
the need for copies.

## Claim

A `RetrievalConfig` parameter on `corpus.search`, whose defaults are today's
retriever, will do three things:
- (a) reproduce the 2026-08-20 dilution comparison
  (`ab_dilution.py`) exactly, for all 8 configurations and every question;
- (b) leave the shipped retriever's output unchanged;
- (c) need less new code than the 168-line copy it replaces.

## Design

- **The seam** is a frozen dataclass,
  `RetrievalConfig(k1, b, heading_weight, stopwords, idf_coverage,
  section_rescue)`, passed as `search(query, chunks, limit=5,
  config=DEFAULT)`. Its defaults equal today's constants: 1.5, 0.75, 3, the
  current 28-word stopword list, raw-count coverage, and no rescue.
- **IDF coverage and section rescue** behave exactly as in
  `ab_dilution.py`:
  - coverage is the IDF-weighted fraction of query terms matched;
  - rescue sets a document's score to the maximum of its document-level
    score and each section's score, where each section is scored as a
    standalone document.
- **The driver**, `evals/retrieval/ab_configs.py`, names the 8
  configurations, runs `search` with each, and writes the top-1 document
  for every question under every configuration to a committed TSV file. It
  prints the same summary as `ab_dilution.py` and contains no tokenizing or
  scoring code.
- **Nothing new is chosen.** No configuration that isn't in the 2026-08-20
  record gets scored. The experiment re-expresses existing comparisons, so
  it adds no selection pressure on the development questions.

## Measures

- **P1, equivalence.** For each of the 8 configurations and each of the 51
  questions, the seam's top-1 document must equal `ab_dilution.top1`'s:
  408 of 408.
- **P2, the shipped retriever is unchanged.** For the 51 QA questions and
  the 9 queries in `packages/server-py/tests/test_retrieval.py`, the full
  result list (doc_id, url, heading, snippet, score) from the new `search`
  with defaults must equal the committed `corpus.search`'s. In addition,
  CI's checks must pass: pytest, ruff, mypy, and the cross-SDK parity check.
- **P3, size.**
  - The total must be under 168 lines, the length of `ab_dilution.py`. The
    total is lines added minus lines removed in `corpus.py`, plus the line
    count of `ab_configs.py`.
  - `ab_configs.py` must contain no scoring code: no `math.` calls, no
    `findall(`, and no BM25 term formula (`+ 1.0)`).

## Decision rule

| Outcome | Condition |
|---|---|
| Supported | P1 408/408; P2 identical, with every check passing; P3 under 168 lines and no scoring code in the driver |
| Refuted | any P1 mismatch; any P2 difference or failing check; P3 of 168 lines or more |
| Inconclusive | a check could not be run |

Any P1 mismatch is reported with its cause, whether a bug in the seam or a
behavioural difference between the copy and the live search. For example,
`ab_dilution.py` picks the top document by document score alone, while
`search` returns the document of the best-ranked passage. A mismatch is not
explained away by redefining the comparison afterwards.

## Controls that must fail

- **The P1 comparison must be able to detect a difference.** Comparing the
  seam's NLTK-stopword configurations against `ab_dilution.py`'s
  current-stopword ones must report mismatches. A deliberately broken seam
  that ignores `idf_coverage` must fail P1 on the IDF configurations.
- **The P2 comparison must be able to detect a difference.** The new
  `search` with `k1=1.2` compared against the committed `search` must
  report differences.

## Stopping rule

Run once. If a check fails because of a bug in the seam, fix the bug, log
it below, and re-run everything. Never adjust the comparison to manufacture
agreement.

## Deviation log

- 2026-10-04: no change to the seam, the configurations or the decision
  rule. The measurement script had two bugs of its own, both fixed before
  any P2 result existed:
  - the pre-seam module wasn't registered before it was loaded;
  - the pre-seam module was pointed at the wrong corpus path.

  P1 and its controls had already printed when the second bug was fixed.
  That fix touched only P2's setup.

## Outcome (2026-10-04): supported

Raw output: `config-seam-check.out`, produced by `config-seam-check.py`.

| Check | Result | Required |
|---|---|---|
| P1 equivalence | 408/408 (8 configurations × 51 questions) | 408/408 |
| P1 controls | NLTK vs current-stopword configs: 4–5 mismatches each; seam ignoring `idf_coverage`: 2 mismatches per IDF configuration | must detect differences |
| P2 shipped output | 60/60 queries identical (51 QA questions + 9 test queries; full result lists) | all identical |
| P2 control | `k1=1.2` differs on 59/60 queries (the 60th is the empty query) | must detect differences |
| P2 CI checks | pytest 24 passed, 2 xfailed; ruff and mypy strict clean; cross-SDK parity: contract, top1 and patterns OK | all pass |
| P3 size | `corpus.py` net +49 lines, plus `ab_configs.py` 81 lines = 130 | under 168 |
| P3 driver | no scoring code | none |

After this outcome, `ab_dilution.py` was deleted (it remains in git
history). `config-seam-check.py` reads it from git at `43dddc7`, so the
checks above still reproduce line for line.

`ab_configs.py` prints the same summary as `ab_dilution.py`, and
`ab_configs.tsv` holds every configuration's top-1 document for every
question. That is the per-question record whose absence cost the
2026-08-05 candidates.
