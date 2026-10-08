# Evidence discipline: the architecture, demonstrated

This repository is a working example of a particular way of building a
knowledge system: a **structured, queryable body of evidence** in which
every claim carries its source, its scope, and the record of how it was
tested — and in which the constraints live in the schema (the data model's
own rules) and the test suite, not in a policy document nobody re-reads.

The domain here is Arm CPU optimization for AI workloads. The domain is
almost beside the point: the same architecture serves any field where
decisions must be made from heterogeneous evidence of varying quality —
market intelligence, medical informatics, systematic review. This page maps
each principle to the place in this repo where it is *implemented and
enforced*, so the claim that the architecture transfers can be inspected
rather than taken on faith.

| Principle | Where this repo implements it |
|---|---|
| **A claim without a permitted source does not enter the system.** | `corpus/manifest.yaml` is the indexing contract: only manifest-listed documents — each with URL, pinned upstream version, fetch timestamp, SHA-256 fingerprint, and license — are ever indexed. A file under `corpus/` with no manifest entry *fails the test suite* (`test_no_undocumented_files_under_corpus`). Derived content obeys the same rule: "a pattern without sources is fabrication" is a literal test assertion (`tests/test_patterns.py`). |
| **Constraints live where the work happens, not in a policy document.** | Provenance is enforced by CI (continuous integration — the automated checks that run on every change): recorded SHA-256 fingerprints must match the committed bytes, so even an in-tree edit to fetched source text fails the build (`tests/test_provenance.py`). Nobody has to remember the rule; the machine won't accept a violation. |
| **Every claim carries its provenance wherever it travels.** | Every search result and every curated pattern the server returns carries its document id and source URL, resolved from the manifest at serve time — the citation an agent sees *is* the provenance record. |
| **Sources that disappear are recorded, never silently dropped.** | A manifest entry for a vanished upstream source keeps its record with a `removed_at:` note and the reason. |
| **Label which mode a claim is in: measurement or conjecture.** | The workbook (`docs/msk-workbook.md`) separates measured results from explanations throughout; Q30/Q30a is a worked case where an *explanation* was made to generate a prediction with an explicit refutation bar, and the outcome corrected the text — one claimed mechanism survived, one was refuted and removed. (That prediction was written in the working session and committed together with its results, so git alone can't show it came first.) Q30b closes that gap: its predictions and decision rules were committed before the run (`demos/kernel-port/experiments/baseline-fairness.md`), and the run script refuses to start until they are. |
| **No summary more confident than the body beneath it.** | Known retrieval failures are strict expected-failure tests (`tests/test_retrieval.py`): documented in code, kept visibly failing, and — if a change fixes them — the marker itself fails, forcing the improvement to be acknowledged. Both language implementations carry the same markers. |
| **Publish the numbers, including the ones that got worse.** | `evals/reports/report.md` commits the full score history: growing the corpus *dropped* the score from 22/30 to 18/30, and the dip is in the record. Current: 41/51 on the development set, with all ten failures categorized by mechanism, and 102/118 on a held-out set whose questions were frozen, and whose pass bar was committed, before the retriever saw any of them (`evals/heldout/plan.md`). The kernel-port headline was cut from 13.5× to 6.5× when that preregistered test showed about half the speedup came from weight reuse an f32 loop can also have, and the comparison in which Apple's Accelerate library beats the port is published next to it (workbook Q30b). |
| **Refutations are findings.** | Two decision records document ideas that did not survive measurement: the semantic-retriever hypothesis (embeddings — meaning-based search — scored 28/48 against word-matching search's 38/48; decision recorded with explicit revisit conditions) and the dilution-fix sketch (8 configurations measured, zero effect, the failure mechanism named). A third came from an audit: the guess that the kernel port's f32 baseline was limited by memory bandwidth, refuted by the preregistered test in workbook Q30b. The system's retrieval choice is a conclusion, not a default. |
| **Ground truth changes only under a stated policy.** | Answer-key widening requires a curator note establishing that every listed document fully answers the question, in a dedicated commit (the † policy) — because editing the answer key is the easiest way to quietly flatter a system. |
| **The absence of a comparison is itself information.** | The eval's failure table categorizes *which kinds* of questions the system cannot yet answer and why; the A/B records state which alternative would need to exist before the decision is revisited. |
| **Cross-checked, not self-certified.** | Two independent implementations (Python and TypeScript) must agree — on the tool contract, on the top-ranked document for all 51 eval questions, and on curated content — enforced in CI on every change (`distribution/schema-sync/`). When a major upgrade of the schema-generating library arrived, the gate proved the contract unchanged rather than anyone asserting it. |
| **State the conditions under which a number is expected.** | The kernel port's error check doesn't use an arbitrary tolerance: the expected relative error is derived (1/15 for uniform test weights), the measurement matches it to two digits, and the conditions under which the derivation holds are stated (`docs/msk-workbook.md` Q31). |

Everything in the table is verifiable from this repository's committed
files and its CI checks. That is the point.
