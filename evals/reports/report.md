# KleidiAI MCP — Retrieval Eval Report

- **Run:** 2026-08-20 (UTC) · harness: promptfoo 0.121.18 · provider: `search_kleidiai_docs` (custom, deterministic)
- **Metric:** top-1 doc — is the top-ranked doc in the question's `expected_doc_ids`?
- **Corpus:** 7 docs · **Questions:** 51 (batch 4 added) · **Retriever: two-level BM25 (unchanged)**

## Score

| Segment | Score |
|---|---|
| Overall | **41/51 (80%)** |
| Frozen 30 (pre-swap baseline subset) | **22/30 (73%)** |
| Batch 4 (tool-use tranche for the two new tools) | **3/3** |
| HARD (deliberate) | **3/5** |

Batch 4 (2026-08-20) adds three tool-use questions covering
`get_kleidiai_pattern` and `plan_kernel_port`, which completed the locked v1
tool surface. All three pass at retrieval; the failure set is unchanged from
the 2026-08-05 run below. Their `expected_tool` grading activates with the
agent provider (still gated on a model API key).

## 2026-08-05 run (retriever swap)

| Segment | Pre-swap | Post-swap | Δ |
|---|---|---|---|
| Overall | 34/48 (71%) | **38/48 (79%)** | +4 |
| Frozen 30 (pre-swap baseline subset) | 20/30 (67%) | **22/30 (73%)** | +2 |
| Batch 3 | 14/18 (78%) | **16/18 (89%)** | +2 |
| HARD (deliberate) | 1/5 | **3/5** | +2 |

## The retriever A/B (the decision record)

Candidates measured on the same 48 questions (`evals/dev_check.py`, then the
winner confirmed by this promptfoo run). No model API key exists in this
environment, so the semantic candidate was a local static-embedding model
(model2vec `potion-base-8M`, no torch):

| Candidate | Overall | Frozen 30 | Verdict |
|---|---|---|---|
| Token-overlap scorer (old) | 34/48 | 20/30 | replaced |
| Chunk-level BM25 | 37/48 | 22/30 | improves, shuffles failures |
| Pure semantic (potion-base-8M) | 28/48 | 16/30 | **refuted** — worse than old scorer |
| BM25 + semantic hybrid (z-sum) | 38/48 | 22/30 | ties lexical winner, adds a dependency — rejected |
| **Doc-level BM25 (coverage-scaled) + chunk-level passage order** | **38/48** | **22/30** | **chosen** — best score, zero new deps |

**The plan's "semantic retriever" hypothesis is refuted at feasible local-model
size.** This corpus's vocabulary is dense and technical; the discriminative
signal is lexical, and an 8M static embedding model actively hurts. What the
weakness categories actually pointed at was BM25's IDF (ubiquitous terms like
"kleidiai" stop dominating) plus doc-level evidence aggregation (the metric
and the tool's purpose are doc citation). Revisit embeddings only with a
markedly stronger model (API key or larger local model) — and let this same
A/B decide again.

Chosen design (in `corpus.py`): doc-level Okapi BM25 scaled by query-term
coverage ranks docs; chunk-level BM25 with weighted headings orders passages
within docs (≤2 per doc for diversity); heading-only chunks feed doc stats but
can't surface as passages. Standard constants (k1=1.5, b=0.75) — not tuned.

## Remaining failures (10, grouped)

| id | want | got | kind | category |
|---|---|---|---|---|
| what-is-kleidiai | kleidiai-readme | kleidiai-matmul-qsi4cx | normal | A residual |
| hard-read-kernel-name | kleidiai-microkernel-names | learnarm-llamacpp-sme2-integration | hard | B residual |
| directory-vs-kernel-name | kleidiai-microkernel-names | kleidiai-readme | normal | B residual |
| what-is-microkernel | kleidiai-readme | kleidiai-microkernel-names | normal | B residual · **new regression** |
| why-pack-matmul | kleidiai-matmul-pack | kleidiai-matmul-qsi4cx | normal | C/D residual |
| enable-kleidiai-llamacpp | llamacpp-build | mlexamples-llamacpp-int4-patch | normal | D1/D2 residual (reviewed, kept) |
| hard-q4-0-kleidiai-format | mlexamples-llamacpp-int4-patch | learnarm-llamacpp-sme2-integration | hard | D2 residual |
| arm-cpu-features-used | llamacpp-build | kleidiai-readme | normal | **new regression** — feature list diluted at doc level |
| integration-languages | kleidiai-readme | llamacpp-build | normal | **new regression** — same mechanism |
| tooluse-run-int4-matmul | kleidiai-matmul-qsi4cx | llamacpp-build | normal | **new regression** — "run/build" vocabulary pull |

Honest accounting: the swap fixed 8 failures (including 2 HARD:
`hard-who-is-kleidiai-for` — the original lexical-gap question from M1 — and
`hard-generic-packing`, plus the entire D2 patch-guide cluster except the
cross-doc HARD) and introduced 4 new regressions, all one mechanism: doc-level
aggregation dilutes a short dedicated section inside a long doc. The two
`xfail(strict)` smoke tests in `packages/server-py/tests/test_retrieval.py`
track this: sme-env-var was un-marked (fixed), micro-kernel-readme was newly
marked (regressed).

## Follow-up A/B: dilution-fix candidates (2026-08-20, all refuted)

The fix sketched at M2 close — score max(doc-level, dedicated-section) — was
implemented and measured (dev_check metric), alongside two other candidate
mechanisms, in all 8 combinations. The measuring script was a copy of the
scorer (`ab_dilution.py`, kept in git history); since 2026-10-04 the same
comparison is `evals/retrieval/ab_configs.py`, which runs the real `search()`
under 8 named configurations and reproduces every result below exactly
(`evals/retrieval/config-seam.md`):

| Candidate | Overall | Frozen 30 | Verdict |
|---|---|---|---|
| Section rescue: max(doc, best section as standalone doc) | 38/48 | 22/30 | **no effect** — see below |
| IDF-weighted coverage | 38/48 | 22/30 | pure trade (fixes `hard-q4-0`, breaks `kleidiai-ggml-types`) — rejected |
| NLTK stopword list (replacing the 28-word list) | 36/48 | 19–21/30 | strictly worse — rejected |
| Combinations of the above | ≤38/48 | ≤22/30 | none beats baseline |

Why the section rescue can't work here: the docs that "steal" the regressed
queries also contain dedicated sections scoring at least as high as the wanted
doc's section (e.g. `what-is-microkernel`, sections scored as standalone docs
under the baseline coverage rule: the naming doc's "Micro-kernel name" section
2.832 vs the README's "What is a micro-kernel?" 2.560; the ordering also holds
under IDF-weighted coverage, 3.375 vs 3.051 — both sections contain "ukernel",
and the question words "what is" are stopwords in every candidate). Under any
max(doc, section) scheme the same doc wins.

Second mechanism surfaced by the debug scores: conversational question words
("try", "want", "programming", "combinations") are *rare in a technical
corpus*, so BM25 gives them high IDF, and a long doc matching one by accident
outscores the canonical doc. IDF cannot separate rare-because-technical from
rare-because-conversational; a standard stopword list doesn't contain these
words. Fixing this would take query understanding beyond lexical retrieval —
out of scope by the "off-the-shelf retrieval only" guardrail.

**Decision: retriever unchanged.** The 4 dilution regressions stay as known
residuals tracked by the strict-xfail smoke tests; revisit only alongside the
semantic-retriever revisit (stronger model, same A/B).

## Prior runs

| Date | Corpus | Questions | Retriever | Score | Notes |
|---|---|---|---|---|---|
| 2026-07-14 | 4 docs | 30 | token overlap | 22/30 (73%) | first 30-question checkpoint |
| 2026-08-05 | 7 docs | 30 (same set) | token overlap | 18/30 (60%) | corpus growth only; † ambiguities identified |
| 2026-08-05 | 7 docs | 30 († resolved) | token overlap | 20/30 (67%) | pre-swap baseline (frozen subset) |
| 2026-08-05 | 7 docs | 48 (batch 3 added) | token overlap | 34/48 (71%) | pre-swap full set; D2 identified |
| 2026-08-05 | 7 docs | 48 | two-level BM25 | 38/48 (79%) | frozen subset 22/30; semantic refuted at 8M |
| 2026-08-20 | 7 docs | 51 (batch 4 added) | **two-level BM25** | **41/51 (80%)** | **current** · batch-4 tool-use questions 3/3; failure set unchanged |
