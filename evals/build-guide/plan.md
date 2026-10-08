# Preregistration: does section coverage fix the build-guide confusion?

- **Written:** 2026-10-08, before any question in the test set exists.
- **Commit:** the commit that adds this file.
- **Status:** confirmatory test of a fix chosen during exploration (below).

## Why

On the held-out set (`evals/heldout/plan.md`), 8 of the retriever's 16
misses confused the two documents that both explain building llama.cpp:
- the llama.cpp build guide;
- Arm's ML-examples guide to the KleidiAI int4 patch.

6 of the patch guide's 14 questions went to the build guide.

## What exploration found (not confirmatory)

The held-out set's misses were studied to find a mechanism. That set is
therefore now development data for this question, alongside the original
51 development questions; neither can test the fix.

- **The mechanism.** A document's score is its BM25 relevance multiplied by
  its *coverage*: the share of the question's words found anywhere in the
  document. The build guide is 2.6 times the average document length, so
  it contains some of almost any question's words somewhere, often in
  unrelated sections. In most misses, the correct document had equal or
  higher BM25 relevance and lost on coverage alone. For example, patch-guide
  question 07 had relevance 13.3 against 10.6, but coverage 10/14 against
  13/14.
- **The conjecture.** Coverage measured over the whole document rewards
  breadth of vocabulary, not where an answer lives. Measuring it within the
  document's best-covering section removes the long document's advantage.
- **Candidates tried on the development data (169 questions)**, all listed:

| Candidate | Original 51 | Held-out 118 | Build-guide confusions (of 118) |
|---|---|---|---|
| C0, shipped | 41 | 102 | 8 |
| **C1, coverage within the best section** | 41 (1 fixed, 1 broken) | 105 (7 fixed, 4 broken) | 3 |
| C2, full length normalization (BM25 b = 1.0), the rival explanation | 41 | 103 | 7 |

C1 was chosen because it follows from the mechanism. It also breaks 5
questions, each between two documents of similar length that trade a
section-level word match. So the effect is a trade, and it needs a fresh
test.

**C1 in code:** `RetrievalConfig(section_coverage=True)` in
`packages/server-py/src/mcp_server_kleidiai/corpus.py`. It is added in this
commit, switched off; with it off, the retriever is unchanged (gate M).

## Claim under test

1. **Q1, mechanism.** Section coverage fixes more build-guide questions than
   it breaks, and at least halves the confusions between the two build
   guides.
2. **Q2, adoption.** It does so without lowering accuracy on a
   representative set of questions.

## The test set: new questions, written blind

- **Core: one question per section.** The held-out procedure is repeated
  exactly, with a fresh writer agent and the same prompt
  (`evals/heldout/prompts/writer.md`), on the same 120 sections. This set
  represents the corpus the same way the held-out set did.
- **Extra: two more questions per build-guide section.** A second fresh
  agent writes two different questions for each of the 52 sections of the
  two build guides (`prompts/writer-extra.md`).
  - **Why:** on the held-out set's 51 build-guide questions, C1's 6 fixes
    against 1 break give p = 0.125. That is too few changed answers to
    decide anything. Roughly three times as many build-guide questions
    should detect an effect of that size.
- **Answer key.** A third fresh agent labels every question with the same
  prompt as before (`evals/heldout/prompts/adjudicator.md`). It sees the
  questions shuffled (seed 20261009), under ids that don't reveal their
  section.
- **Assembly and freeze.** `build_set.py` joins the outputs without editing
  anything; a question no document answers is excluded. Everything is
  committed and pushed before any search runs on these questions.

None of the agents sees the retriever, its results, the development
questions or the held-out questions.

## Measures and decision rule

All scoring is by `score.py`, once, with the promptfoo provider's call:
search the question, limit 5, top-1 document.

**Q1, on the build-guide questions** (core and extra, about 155):
- **net** = questions C1 fixes − questions C1 breaks, against C0;
- **p**, from an exact sign-flip test at the section level. Questions from
  the same section aren't independent, so each section's net change is the
  unit;
- **confusions**: questions from one build guide answered with the other,
  for C0 and for C1.

| Outcome | Condition |
|---|---|
| Inconclusive: nothing to fix | C0 has fewer than 5 confusions |
| **Supported** | net > 0, p < 0.05, and C1's confusions ≤ half of C0's |
| **Refuted** | net ≤ 0, or C1's confusions ≥ C0's |
| Inconclusive | otherwise |

**Q2, on the core set** (one question per section, about 118): C1 becomes
the shipped default only if Q1 is supported **and** C1's core accuracy is at
least C0's. Otherwise the shipped retriever stays as it is, and C1 stays an
option that is switched off.

## Validity gates

If any gate fails, the measurement is invalid, whatever the scores.
- **M:** with the option off, the retriever's full result lists equal the
  shipped retriever's (at `c494960`) on every question in the test set,
  the development set and the held-out set. Checked on the existing
  questions before this commit: 287/287.
- **A, B, C:** the held-out plan's gates, on the core set: oracle at least
  90%, random-document baseline at most 30%, and shifted questions no more
  than 10 points above the constant baseline.

## Secondary measures (no decision attached)

- **S1, the rival explanation.** Full length normalization (C2) on the same
  questions. The conjecture predicts it fixes far fewer confusions than C1,
  because length alone isn't the cause.
- **S2:** McNemar's exact test on the build-guide questions, ignoring
  sections, for reference.
- **S3:** a correct document anywhere in the 5 results, for C0 and C1.
- **S4:** core accuracy by source document, for C0 and C1.
- **S5:** how many test questions are near-duplicates of a held-out question
  (shared words ≥ 50%). Those questions were seen while choosing C1, so the
  net change is also given without them.
- **S6:** the development-data numbers in the table above, recomputed.

## What the published numbers become

- **If C1 is adopted:**
  - both servers change together, Python and TypeScript, and the
    cross-SDK parity check must pass;
  - the eval report and README quote the core set's C1 score, labelled as
    the set that made one preregistered adoption decision;
  - the held-out set's 102/118 stays in the record as the shipped
    retriever's score before the change.

  A score on questions untouched by any decision would need a new set,
  written later.
- **If C1 isn't adopted:** the shipped retriever is unchanged, and the
  held-out score of 102/118 still describes it. The new questions' C0 score
  is reported beside it.

## Stopping rule

- **Each agent runs once.** If an agent's output is malformed or
  incomplete, that step is rerun from scratch before the freeze, and logged.
- **Scoring runs once.** A bug in `score.py` is fixed, logged and rerun in
  full.
- **No question or label changes after the freeze,** for any reason.

## Limitations, stated in advance

- **C1 was chosen after studying the held-out misses.** The new questions
  come from the same 120 sections, so a fix fitted to those sections'
  wording could look better than it is. S5 checks the closest overlaps.
- **The questions are written by language-model agents, not real
  developers,** and the agents may share blind spots.
- **Q2's bar, "no lower than C0", is strict about the direction but not the
  size.** A fix that loses one core question is not adopted, even though one
  question is within noise.

## Deviation log

- 2026-10-08: **the questions were committed before the answer key**
  (`9bac228`), not together with it at the freeze (`1254ade`). As in the
  held-out run, this only moved part of the freeze earlier; no search had
  run on any question at either point.
- **No other deviation.** Each agent ran once, no question or label was
  edited, and `score.py` ran once on the frozen set.

## Outcome (2026-10-08): Q1 inconclusive; section coverage is not adopted

Raw output: `score.out`; every question's answer under C0, C1 and C2:
`results.tsv`.

**The set:**
- the core writer wrote 116 questions and skipped 4 sections, each with a
  reason;
- the extra writer wrote 95, one per section for 7 sections that are a
  single command, and none for the license notice;
- the labeller judged all 211 answerable, and 15 have more than one correct
  document.

146 questions come from the two build guides.

| Check | Result | Required |
|---|---|---|
| Gate M: option off = shipped | 380/380 identical result lists | all |
| Gates A, B, C | oracle 116/116; random 15.8%; shifted 26/116 against a constant baseline of 37/116 | as planned |
| **Q1:** build-guide questions, C0 → C1 | 129/146 → 133/146: **6 fixed, 2 broken, net +4** | net > 0 |
| Q1: section-level sign-flip test | **p = 0.22** (6 sections changed) | p < 0.05 |
| Q1: confusions between the guides | **13 → 9** | at most 6 |
| Q2: core set, C0 → C1 | 100/116 → 104/116 (7 fixed, 3 broken) | applies only if Q1 is supported |

**Q1 is inconclusive.**
- The change goes the predicted way: net +4, and fewer confusions.
- It's too small to rule out chance (p = 0.22), and the confusions didn't
  halve.

Of the shipped retriever's 13 confusions, C1 fixed 5, left 7, and sent 1
to a different wrong document; it also created 2 new ones.

**So the shipped retriever stays as it is.** Section coverage remains an
option that is switched off. The held-out score of 102/118 still describes
the shipped retriever. On these new questions, the shipped retriever scores
100/116 (86.2%, 95% Wilson 78.8%–91.3%) on the core set, which is
consistent with it.

**Secondary measures:**
- **S1, the rival:** length normalization (C2) fixed 1 build-guide
  question, broke none, and left 12 confusions. As predicted, length alone
  doesn't explain the confusion: section coverage moves it, length
  normalization barely does.
- **S2:** McNemar's test, ignoring sections, gives p = 0.29.
- **S3:** a correct document is in the 5 results for 115/116 core
  questions, under both C0 and C1.
- **S4:** C1's core gains are spread across the naming guide (+2), the
  build guide (+1) and the patch guide (+1). The packing guide gains 2 and
  loses 2.
- **S5:** 49 of the 146 build-guide questions are near-duplicates of a
  held-out question studied while choosing C1. **Without them, the net
  change is +1 of 97.** Most of the effect sits in questions that resemble
  the ones the fix was chosen on.
- **S6:** the development-data numbers are reproduced: 41/51 and 102/118
  for C0; 41/51 and 105/118 for C1; 41/51 and 103/118 for C2.

**What this teaches:**
- **The mechanism is right in direction.** Coverage counted over a whole
  long document does pull questions toward it, and counting it per section
  pulls some back. Length normalization doesn't.
- **The size didn't hold up.** On fresh build-guide questions, the net gain
  is 4 of 146 (2.7%), under a third of the 5 of 51 (9.8%) seen on the
  held-out questions, and it nearly vanishes on questions unlike the ones
  studied. Choosing a fix by looking at specific
  misses fitted it partly to those questions' wording.
- **The confusion is also rarer than the held-out misses suggested.** The
  build guides were confused on 13 of 146 fresh questions (9%), against 8
  of 51 (16%) on the held-out set.
- **For any later conjecture:** a set written from the same 120 sections
  will resemble the earlier ones; a third of these questions did. A clean
  test of a new idea needs either questions of a different kind or new
  sections.
