# Preregistration: a held-out question set for the retrieval eval

- **Written:** 2026-10-08, before any held-out question exists.
- **Commit:** the commit that adds this file.
- **Status:** confirmatory.

## Why

The published retrieval score, 41/51 (80%), comes from a **development
set**: the same 51 questions were used to choose the retriever in August.
A score on the questions a design was chosen on tends to run high, because
the choice favours whatever happens to work on those particular questions.
The README and the question file both say so. The v1 scope calls for
scoring on a **held-out set**: questions never used for any design choice,
scored once.

## Claim under test

The development score generalizes. On fresh questions, the shipped
retriever's top-1 accuracy is within 10 percentage points of 80%, that is,
at least 70%.

Rival explanations if the held-out score comes out lower:
- **Overfitting:** the retriever was chosen on the development questions.
- **Phrasing:** the new questions share fewer words with the documents,
  which hurts a word-matching retriever. Secondary measure S6 checks this.
- **Topic mix:** the new set covers every section, while the development
  set was hand-picked. S5 checks this.
- **Label noise:** the answer key is wrong for some questions. Gate A and
  S2 and S4 check this.

If it comes out higher, the likeliest rival is easier phrasing (S6).

## What is being tested

- **The retriever:** `search()` in
  `packages/server-py/src/mcp_server_kleidiai/corpus.py` with its default
  settings, unchanged since `ea01c59`.
- **The corpus:** the 7 documents in `corpus/manifest.yaml`, unchanged.
- **The call:** the same one the promptfoo harness makes
  (`evals/mcp_provider.py`): search the question with a limit of 5, and
  take the document of the first result.

## How the questions are made

1. **Sections.** The server splits each document into sections at its
   headings. Every section with at least 30 words is used: 120 sections.
   Using all of them leaves no sampling choice to make. `sections.py` lists
   them, with a hash of each section's text, in `sections.tsv`.
2. **Questions, written blind.** A separate language-model agent, started
   fresh for this task, gets only the prompt in `prompts/writer.md` and a
   file of the 120 sections. It writes one question per section, as a
   developer would ask it, without copying 4 or more consecutive words from
   the section. It may skip a section that no developer would ask about
   (a license notice, a list of links), and must say why. It never sees the
   retriever, its results, the development questions or this repository.
3. **Answer key, labelled blind.** A second fresh agent gets only the
   prompt in `prompts/adjudicator.md`, the full text of the 7 documents and
   the questions. The questions are in a shuffled order (seed 20261008),
   under ids that don't reveal their section. For each question, it lists
   every document that answers it.
4. **Assembly.** `build_set.py` joins the two outputs mechanically:
   - The correct documents for a question are its source section's
     document plus any others the second agent listed.
   - A question no document answers, in the second agent's judgment, is
     excluded.
   - Nothing else is edited or removed: no question, no label.
5. **Freeze.** The questions, both agents' raw outputs and the assembled
   `questions.yaml` are committed and pushed before the retriever sees any
   question. The questions are read only to check the files' format; no
   search is run on them until the freeze is pushed.
6. **Score once.** `score.py` scores the frozen set and writes `score.out`
   and `results.tsv`.

## Primary measure

Top-1 document accuracy: the share of questions whose first result comes
from a correct document. It is reported with a 95% Wilson interval, a
standard range for a proportion that stays accurate at these sizes.

## Decision rule

| Outcome | Condition (95% Wilson interval) |
|---|---|
| **Supported:** the development score generalizes | lower end ≥ 70% |
| **Refuted:** the development score overstates by more than 10 points | upper end < 70% |
| **Inconclusive** | the interval contains 70% |

At the likely size of about 110 questions, this means:
- supported at about 79% or more;
- refuted at about 61% or less;
- inconclusive in between.

Supporting the claim needs a score close to 80%, because "within 10
points" must be shown, not merely not ruled out.

**Whatever the outcome, the published numbers change.** The README and the
eval report will lead with the held-out score and its interval, and give
the development score second, labelled as such.

## Validity gates

These check the measurement, not the retriever. If any gate fails, the
result is reported as an invalid measurement, whatever the score, and the
cause is investigated.

- **A, the answer key and pipeline can succeed.** Searching with each
  question's own source section as the query must put the source document
  first for at least 90% of questions.
  - Run before any question existed, on all 120 sections: 120/120.
- **B, the metric can fail.** A retriever that picks a document at random
  must be expected to score at most 30%. This would fail only if the answer
  key listed so many correct documents per question that guessing worked.
- **C, the score depends on the question.** Scoring each question with
  another question's result (a fixed shuffle, seed 20261008) must score no
  more than 10 points above always answering the most common document.

## Secondary measures (no decision attached)

- **S1:** the share of questions with a correct document anywhere in the 5
  results, which is what an agent using the tool actually sees.
- **S2:** accuracy when only the source document counts as correct.
- **S3:** the number of near-duplicates of a development question (shared
  words ≥ 50% by Jaccard), and the accuracy without them.
- **S4:** the number of questions where the second agent didn't list the
  source document, and the accuracy without them.
- **S5:** accuracy by source document, and the average of the per-document
  accuracies, so the largest document doesn't dominate.
- **S6, a phrasing check:**
  - the share of each question's words found in its correct document, for
    the held-out and development sets;
  - the number of questions that repeat 4 or more consecutive words of
    their section.

## Checks already run (no held-out question involved)

- `dev_check.py` reproduces the development score: 41/51.
- `score.py`, run on the development set, also gives 41/51. Gate A is
  empty there, because development questions have no source section.
- The oracle check for gate A: 120/120 (above).

## Rules after scoring

- **The held-out set is never used to choose or tune anything.** It is
  scored for reporting, on releases. If it is ever used to pick between
  designs, it becomes a development set, and a new held-out set is needed.
- **Misses are listed, not fixed.** `results.tsv` records every miss. They
  may inform a future conjecture, which would be tested on new questions.

## Stopping rule

- **Each agent runs once.** If an agent's output is malformed or
  incomplete, that whole step is rerun from scratch before the freeze, and
  logged.
- **Scoring runs once.** If `score.py` has a bug, it is fixed, logged and
  rerun in full.
- **No question or label is changed after the freeze,** for any reason.

## Limitations, stated in advance

- **The questions are written by a language model from the sections, not
  asked by real developers.** They measure retrieval on questions of that
  kind. Real queries may be vaguer.
- **The writer and the labeller are agents of the same kind,** so their
  judgments may share blind spots.
- **Every section counts once,** so documents with many sections (the
  llama.cpp build guide has 37) weigh more. S5 reports the balanced view.
- **This covers retrieval only.** Tool-use scoring still waits on the agent
  provider.

## Deviation log

- 2026-10-08: **the questions were committed earlier than planned.** The
  writer's output was committed (`3f2a400`) before the answer key existed,
  rather than together with it at the freeze (`41c2390`). This only moved
  part of the freeze earlier; no search had run on any question at either
  point.
- **No other deviation.** Each agent ran once, no question or label was
  edited, and `score.py` ran once on the frozen set.

## Outcome (2026-10-08): supported

Raw output: `score.out`; every question's result: `results.tsv`.

| Check | Result | Required |
|---|---|---|
| **Primary:** top-1 accuracy | **102/118 = 86.4%** (95% Wilson 79.1%–91.5%) | lower end ≥ 70% to support |
| Development set, for reference | 41/51 = 80.4% (67.5%–89.0%) | — |
| Gate A, oracle | 118/118 | ≥ 90% |
| Gate B, random-doc baseline | 16.2% | ≤ 30% |
| Gate C, shifted questions | 20.3%, against 31.4% for always answering the llama.cpp build guide | ≤ 41.4% |

All three gates passed, so the measurement is valid. The interval's lower
end, 79.1%, is above 70%: the development score did not overstate the
retriever's accuracy on fresh questions of this kind. The held-out estimate
is in fact higher, and the two intervals overlap.

**Set size:** the writer wrote 118 questions and skipped 2 sections (a
license notice, and a block that only sets example values). The labeller
judged all 118 answerable, so none were excluded. 12 have more than one
correct document.

**Secondary measures:**
- **S1:** a correct document is somewhere in the 5 results for 117/118
  (99.2%).
- **S2:** counting only the source document as correct, 99/118 (83.9%).
- **S3:** 3 questions are near-duplicates of development questions;
  without them, 99/115 (86.1%).
- **S4:** the labeller listed the source document for every question.
- **S5:** by source document:
  - matmul packing guide: 10/11;
  - int4 matmul guide: 15/15;
  - naming guide: 12/14;
  - KleidiAI README: 13/17;
  - Arm learning path: 10/10;
  - llama.cpp build guide: 35/37;
  - Arm ML-examples int4 patch guide: **7/14**.

  The doc-balanced average is 85.4%.
- **S6, phrasing:** on average 80% of a held-out question's words appear
  in its correct document, against 79% for the development questions, so
  the new questions aren't wordier matches. 4 questions repeat a 4-word
  run from their section, against the writer's instructions. The phrases
  are short and generic ("in the llama cpp", "size of the packed"). They
  stay in the set, because the plan allows no edits.

**The misses (exploratory, no test attached).** 8 of the 16 misses confuse
the two documents about building llama.cpp with KleidiAI: the llama.cpp
build guide and the Arm ML-examples patch guide.
- 6 of the patch guide's 7 misses went to the build guide. Its steps for
  Android, Linux boards and Windows were retrieved as the general guide's.
- 2 build-guide questions went the other way.

Of the rest:
- 4 questions about KleidiAI itself (what it is, what building it needs,
  x86 support, example programs) went to the llama.cpp build guide;
- 2 naming-guide questions went to the KleidiAI README;
- 1 patch-guide question went to the README;
- 1 packing-guide question went to the Arm learning path.

Overlapping build instructions in two documents is the retriever's main
weakness on this set. Any fix would be a new conjecture, tested on new
questions, not on these.

**Why the held-out score could be higher (interpretation, not tested).**
The development set was partly built to find failures: it includes 5
questions tagged HARD, chosen because an earlier retriever failed them.
The held-out set takes every section once, with no difficulty selection.
S6 rules out one rival, that the new questions simply repeat the
documents' words more often.
