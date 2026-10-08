# The MSK Workbook — mcp-server-kleidiai, fully worked

**MSK** is short for **mcp-server-kleidiai**, this repository's project.
This workbook is a set of questions about the project, each followed
immediately by its complete answer with the reasoning shown — no blanks, no
gotchas, no busywork. It is written to be generous to the reader: every
term of art is explained in plain language the first time it appears, the
numbers are real (measured on this repo's own evaluation set and on an
Apple M5 Pro laptop chip), derivations are carried through step by step,
and each answer names its primary source so you can check the claim against
the text instead of trusting the summary.

Current as of 2026-08-20 (milestones M1–M2 shipped; M3 rehearsed, recording
pending; M4/M5 machinery built, publishes pending).

## Baseline vocabulary

A handful of terms appear everywhere, so here they are once, up front:

- **AI agent** — an AI assistant that doesn't just chat but *acts*: it can
  call tools, run searches, and use the results to finish a task.
- **MCP (Model Context Protocol)** — an open standard that works like a
  universal power socket between AI assistants and external tools or
  knowledge. Any assistant that speaks MCP can plug into any MCP server.
- **MCP server** — a small program that offers "tools" (callable functions
  with documented inputs and outputs) to agents over that socket.
- **Arm** — the processor family in essentially all phones and, these
  days, in Apple's M-series Macs, Snapdragon Windows laptops, and Amazon's
  Graviton server chips.
- **KleidiAI** — Arm's open-source library of *micro-kernels*: tiny,
  hand-optimized routines that each do one performance-critical math
  operation (chiefly matrix multiplication, the math AI models run
  constantly) as fast as a given Arm chip allows.
- **llama.cpp** — a popular open-source program for running large language
  models locally on your own machine, no cloud involved.
- **Corpus** — the curated collection of source documents this server
  searches; the project's knowledge base.
- **Quantization** — storing numbers in fewer bits (say, 4 instead of 32)
  to save memory and time, at a small, quantifiable cost in precision.
- **Eval(s)** — evaluations: fixed, repeatable measurements of quality
  against a fixed set of test questions.
- **CI (continuous integration)** — an automated checker that builds the
  project and runs all its tests on every change, so breakage is caught
  the moment it happens.

Sources of truth: `CLAUDE.md` (operating handbook), `v0-decisions.md`
(locked decisions), `architecture.md` (how the pieces fit),
`evals/reports/report.md` (the measured record), `corpus/manifest.yaml`
(provenance contract), `demos/kernel-port/README.md` (port + benchmark).

---

## 1. The pitch, the wedge, the moat

**Q1. In one sentence, what is this project?**

An MCP server giving AI agents structured, provenance-cited access to
KleidiAI + llama.cpp Arm-optimization expertise — as of August 2026 the
only knowledge server found in that niche (adjacent MCP servers benchmark
KleidiAI; none serve its documentation) — with the retrieval quality
measured and committed rather than asserted. ("Provenance" means a documented chain of origin: where every
piece of knowledge came from, when it was fetched, and proof it hasn't been
altered since.)

**Q2. What is KleidiAI, and how does it reach users who have never heard of it?**

KleidiAI is Arm's open-source library of micro-kernels, each targeting
specific Arm CPU features — hardware capabilities that newer chips add,
with names like **dotprod**, **i8mm**, **SVE**, and **SME** (for example,
i8mm is dedicated circuitry for 8-bit integer matrix math). It reaches
ordinary users through llama.cpp, which uses KleidiAI as its CPU
matrix-math backend on Arm when built with the switch
`GGML_CPU_KLEIDIAI=ON`. So everyone running llama.cpp on an M-series Mac,
Snapdragon X laptop, or Graviton server is already running KleidiAI without
knowing it. That huge implicit install base is why this narrow niche is
valuable. (Source: `corpus/llamacpp/build.md` § Arm KleidiAI; `about.md`.)

**Q3. Why is the wedge "llama.cpp + KleidiAI" rather than all of KleidiAI?**

(A "wedge" is a deliberately narrow entry point into a market.) Because
"best in genre" on day one requires a genre small enough to actually
dominate. All of KleidiAI is too broad to curate exhaustively; the
llama.cpp integration is the hottest agentic-AI framing of 2026 and lets
one corpus, one eval set, and one demo reinforce each other. Growth is
additive, not a redesign: v1.5 adds coverage of ExecuTorch (another
on-device AI runtime, from the PyTorch project), v2 adds KleidiAI's core C
kernels — corpus and eval extensions, same server. (Source:
`v0-decisions.md` § Wedge.)

**Q4. Anyone can stand up an MCP server in an afternoon. What exactly is defensible here?**

Three things, in order of importance:

1. **The corpus** — hand-curated for this exact niche, with provenance
   (source URL, pinned version, fetch timestamp, SHA-256, license)
   recorded for every entry and enforced by tests. (A **SHA-256** is a
   cryptographic fingerprint of a file: change even one byte and the
   fingerprint changes, so it proves content hasn't been tampered with.)
   Reproducing the scaffolding is trivial; reproducing careful curation is
   not.
2. **The evals** — a 51-question *development* set with committed score
   reports (41/51). "Development" because the same questions were used to
   choose between retriever designs, so that score could run high. A
   separate *held-out* set, 118 questions never used for any design choice
   and scored once, gives 102/118 (Q22a). The reports include honest
   failures. Most portfolio projects
   assert reliability; this one demonstrates it, including two
   on-the-record refutations of ideas that didn't survive measurement (§6).
3. **The demo** — a real kernel port whose speedup is measured against
   fair baselines (6.5× over an f32 loop with the same weight reuse, Q30b),
   staged so the recorded agent session is verifiably genuine (§7).

The retrieval itself is deliberately boring (§4). (Source: `CLAUDE.md`
§ Load-Bearing Constraints.)

---

## 2. MCP and the tool surface

**Q5. What is MCP mechanically — what actually happens when an agent uses this server?**

Under the hood MCP is **JSON-RPC** — a simple convention for sending named
commands and getting replies, encoded as JSON text — carried over a
transport, here **stdio** (the plain text input/output channel every
program has). The client launches the server process, sends an `initialize`
greeting so both sides agree on capabilities, then `tools/list` to discover
the tool surface — each tool arrives as a name, a description, and a
**JSON-schema**: a machine-readable statement of what parameters the tool
accepts and which are required. Those schemas aren't written by hand; they
are generated from ordinary type declarations by a library (**pydantic** in
Python, **zod** in TypeScript). A `tools/call` request names a tool and
passes arguments; the reply is a list of content items (here, text items
carrying JSON). Both of this repo's servers were verified with a real
client round-trip over stdio, including cross-language — the Python MCP
client driving the TypeScript server. (Source:
`packages/server-py/tests/test_server.py`; the SDKs.)

**Q6. Name the three tools and the distinct job of each.**

1. `search_kleidiai_docs(query, limit=5)` — ranked passages from the
   corpus, every result carrying its document id and source URL so answers
   cite real docs. The general-purpose entry point.
2. `get_kleidiai_pattern(pattern_id="")` — curated recipes ("patterns")
   condensed from the corpus: enabling KleidiAI in llama.cpp, the int4
   micro-kernel set, decoding a kernel filename, how llama.cpp selects
   kernels. Called with no id, it returns the catalog — so an agent can
   discover what patterns exist without a separate listing tool.
3. `plan_kernel_port(rhs_quant, cpu_features, rhs_layout="nxk")` — the
   task-shaped tool wired to the killer demo: give it a weight-quantization
   scheme, the target CPU's features, and the weight layout, and it returns
   the exact micro-kernel set, call order, where the packing parameters
   come from, build flags, and constraints.

The v1 scope locked "at minimum" these three shapes — retrieval, lookup,
task — in 2026-05. (Source: `v0-decisions.md` § v1 Scope;
`packages/server-py/src/mcp_server_kleidiai/server.py`.)

**Q7. The planner could easily "help more" by guessing kernels for undocumented cases. Why doesn't it?**

Because the reliability thesis is *cited or silent*. For quantization/CPU
combinations the corpus doesn't document, `plan_kernel_port` returns
`supported: false` with an explanation and a pointer to
`search_kleidiai_docs` — never an invented kernel name. Kernel names are
exactly the kind of long, structured identifier a language model will
plausibly **hallucinate** (produce convincing-looking but false output); a
tool that refuses to is worth more than one that usually gets it right.
(Source: `patterns.py::plan_port`, final branch; test
`test_plan_port_refuses_undocumented_paths`.)

**Q8. Patterns are written by the project, not fetched. How is the no-fabrication rule extended to them?**

Two mechanisms. Content rule: a pattern may not state a fact its cited
docs don't contain — it condenses, never invents. Mechanical rule: every
pattern carries `sources:` (document ids from the manifest); a test fails
if a pattern cites an unknown id or has no sources at all ("a pattern
without sources is fabrication"), and source URLs are resolved from the
manifest at serve time, so the citation an agent sees *is* the provenance
record itself. (Source: `patterns.yaml` header; `tests/test_patterns.py`.)

---

## 3. Corpus and provenance

**Q9. Walk through exactly what a corpus entry consists of, and what each field is for.**

The **manifest** (`corpus/manifest.yaml`) is the ledger listing every
document in the corpus. Its entry for the int4 guide:

```yaml
- id: kleidiai-matmul-qsi4cx            # stable handle used by evals, patterns, results
  url: https://github.com/ARM-software/kleidiai/blob/main/docs/matmul_qsi4cx/README.md
  raw_url: https://raw.githubusercontent.com/...   # what was actually fetched
  commit: b87ef9c94f45f11c81a6b1fdaed1b2b45ea58c0c # pins WHICH version of the doc
  fetched_at: 2026-08-05T23:06:36Z                 # when it was true
  sha256: 0e99c743...                              # proves the committed bytes ARE the fetched bytes
  path: kleidiai/matmul-qsi4cx-README.md           # where it lives in-tree
  license: Apache-2.0                              # redistribution terms travel with the doc
  description: ...                                 # what the doc canonically answers
```

(A **commit** here is a snapshot identifier in the source project's
history — "pinning" to it means recording exactly which version was
copied.) The committed file must be byte-identical to the fetched source —
no paraphrase, no trimming, no annotations. The agent reasons over real
source text or over nothing.

**Q10. How is that contract enforced, rather than merely stated?**

Three tests in `tests/test_provenance.py`, run in CI on every change:

1. every entry has all provenance fields;
2. every committed file's SHA-256 fingerprint equals the manifest's
   recorded one — so an in-tree edit to fetched content fails the suite;
3. no file exists under `corpus/` without a manifest entry.

A source that disappears upstream keeps its entry with a `removed_at:`
note; removal is recorded, never silent.

**Q11. Why is the corpus committed in-tree instead of fetched on demand?**

Self-contained review (a reviewer needs no network), offline-reproducible
evals (scores can't drift because a website changed), and protection
against link rot. The cost is repository size — acceptable when
reviewability is the point. A subtlety that surfaced later: an *installed*
copy of the server also has no repository to read from, which is why
release builds stage a copy of the corpus inside the package (§9).
(Source: `v0-decisions.md` § Corpus storage.)

**Q12. What's the licensing situation of the corpus, and where's the one obligation to remember?**

The project is **Apache-2.0** (a permissive open-source license — use
freely, keep the attribution — matching upstream KleidiAI). Corpus
documents retain their original licenses, recorded per entry: the four
KleidiAI docs are Apache-2.0, the llama.cpp build doc and the ML-examples
patch guide are **MIT** (another permissive license), and the
learn.arm.com SME2 integration doc is **CC-BY-SA-4.0** — a "share-alike"
license, meaning redistribution requires attribution (given in `NOTICE`)
and any *adaptation* of that document would have to carry the same
license. Verbatim redistribution with attribution, which is all this repo
does, is fine under all three. (Source: `corpus/manifest.yaml` license
fields; `NOTICE`.)

---

## 4. Retrieval, fully worked

**Q13. Describe the retrieval pipeline end to end, naming every stage.**

1. **Load**: every manifest-listed doc is split at markdown headings into
   **chunks** (sections); each chunk carries its doc id and URL.
2. **Tokenize**: lowercase the text and break it into **tokens** — runs of
   letters and digits — then drop a 28-word **stopword** list (words like
   "the" and "of" that carry no search signal). "micro-kernel" becomes two
   tokens, `micro` and `kernel`.
3. **Index**: count each token's frequency per chunk (heading words
   counted 3×) and, aggregated, per doc; record lengths and how many
   chunks/docs each token appears in.
4. **Doc ranking**: score whole docs with **BM25** — a classic
   search-engine ranking formula from the 1990s (the name is just "Best
   Match, formula 25") — scaled by *coverage*, the fraction of the query's
   distinct words the doc contains. This decides *which docs canonically
   answer*.
5. **Passage ordering**: chunk-level BM25 orders passages within each doc;
   at most 2 passages per doc so runner-up docs still surface.
6. **Result**: doc id, URL, heading, a query-focused snippet, and the
   doc-level score (that's what the cross-doc ordering means).

Standard constants: k1 = 1.5, b = 0.75. Nothing tuned. (Source:
`corpus.py`, whose module docstring is the design record.)

**Q14. Write down the BM25 formula as implemented, and compute the actual IDF values for this corpus.**

Two ingredients per matched term *t*: its frequency **f(t)** in the
document being scored, and its **IDF** — *inverse document frequency*, a
measure of how rare the term is across all documents. Rare words carry
more information ("qsi4cxp" tells you more than "kernel"), so they score
higher. For a document of length *L* (average length *avg*):

    score(t) = idf(t) · f(t)·(k1+1) / (f(t) + k1·(1 − b + b·L/avg))
    idf(t)   = ln( (N − d(t) + 0.5) / (d(t) + 0.5) + 1 )

where N is the number of documents, d(t) is how many contain the term, and
ln is the natural logarithm. The right-hand fraction in score(t) grows with
f(t) but *saturates* — the tenth mention adds far less than the first —
and the L/avg part discounts long documents, which match everything a
little.

At the doc level N = 7 here, so IDF takes exactly seven possible values.
Working each one:

| in d docs | idf = ln((7−d+0.5)/(d+0.5) + 1) | value |
|---|---|---|
| 1 | ln(6.5/1.5 + 1) = ln(5.333) | **1.674** |
| 2 | ln(5.5/2.5 + 1) = ln(3.200) | **1.163** |
| 3 | ln(4.5/3.5 + 1) = ln(2.286) | **0.827** |
| 4 | ln(3.5/4.5 + 1) = ln(1.778) | **0.575** |
| 5 | ln(2.5/5.5 + 1) = ln(1.455) | **0.375** |
| 6 | ln(1.5/6.5 + 1) = ln(1.231) | **0.208** |
| 7 | ln(0.5/7.5 + 1) = ln(1.067) | **0.065** |

So a term appearing in one doc is worth ~26× a term appearing in all
seven. These are the exact values observed when debugging real queries:
`exploit` 1.67 (one doc), `ukernel` 1.16 (two), `int4` 0.83 (three),
`kernel` 0.37 (five), `kleidiai` 0.21 (six).

**Q15. Work a real ranking: why does "What is a micro-kernel (ukernel) in KleidiAI?" retrieve the naming doc instead of the README, whose dedicated section answers it?**

Query terms after stopwording: `micro`, `kernel`, `ukernel`, `kleidiai`,
with IDFs 0.21, 0.37, 1.16, 0.21. Measured doc-level scores
(coverage-scaled BM25): naming doc **4.253**, README **3.220**. The one
high-IDF term doesn't just fail to discriminate — it backfires: the exact
token `ukernel` appears 10× in the naming doc and once in the README (the
int4 guide has only the plural `ukernels`, which the tokenizer treats as a
different token), and the naming doc is *entirely about* micro-kernel
names, so its frequencies for `micro`/`kernel` saturate higher too. Even
section-vs-section the README loses: scored as standalone docs under the
same coverage rule, its "What is a micro-kernel?" section reaches 2.560
against the naming doc's "Micro-kernel name" section at 2.832 — and the
words that would discriminate ("what is", a definition-shaped question)
are stopwords in every configuration tried. This is why the
"dedicated-section rescue" fix was refuted (§6): under any max(doc,
section) scheme, the same doc still wins. The failure is tracked by a
strict expected-failure test (Q20), not hidden. (Source:
`evals/reports/report.md` § Follow-up A/B; `tests/test_retrieval.py`.)

**Q16. Why coverage-scale the doc score at all?**

Raw BM25 lets a long document that merely *repeats one rare query term*
outrank the document that answers the whole query. Multiplying by
(matched distinct terms ÷ total query terms) makes breadth of match count.
Its known cost, discovered by measurement: long docs also *buy* coverage
by matching generic question words ("want", "try", "set"), which is one of
the two residual failure mechanisms (§6, Q26). (Source: comment above
`doc_score` in `corpus.py::search`.)

**Q17. Why weight heading terms 3×, and why cap passages at 2 per doc?**

Heading weight: a section *titled* for the query should outrank a section
that merely mentions the terms in its body — a cheap version of BM25F, the
variant of BM25 that scores document fields (titles, body) differently.
Cap: the results list serves an agent, which wants the winning doc's best
passages *and* visibility of runner-up docs; without the cap, one doc's
many matching sections would monopolize the list. (Source: the constants
comment in `corpus.py`.)

---

## 5. The eval discipline

**Q18. Describe the metric, the current score, and what the score history has actually been.**

Metric: **top-1 doc** — is the highest-ranked document's id among the
question's acceptable answers (`expected_doc_ids`)? The scoring is
deterministic — same input, same output, every time — with no AI model and
no API key in the loop. Current committed record on the development set:
**41/51 (80%)** overall; the frozen 30-question subset 22/30;
deliberately-HARD questions 3/5. On the held-out set: **102/118 (86%)**
(Q22a).

History (all committed in `evals/reports/report.md`):

| Date | Set | Retriever | Score |
|---|---|---|---|
| 2026-07-14 | 30 q, 4 docs | token overlap | 22/30 |
| 2026-08-05 | 30 q, 7 docs | token overlap | 18/30 → 20/30 after † resolutions |
| 2026-08-05 | 48 q | token overlap | 34/48 |
| 2026-08-05 | 48 q | two-level BM25 | 38/48 |
| 2026-08-20 | 51 q (batch 4) | two-level BM25 | 41/51 |

Note the honest dip: growing the corpus alone *lowered* the score
(22→18/30) because new docs create new confusion; that dip is recorded,
not smoothed over.

**Q19. What is the † widening policy, and why does ground truth need a policy at all?**

**Ground truth** is the answer key — which documents count as correct for
each question. Changing it is the easiest way to quietly flatter a system
("the answer key was wrong, not the retrieval"), so it has rules: a
question's acceptable answers may be widened only when a curator note
establishes that every listed doc contains a complete, direct answer, and
only in dedicated commits so the change is visible and reviewable in
isolation. Never tune questions to make the server look better; add HARD
questions deliberately. (Source: `CLAUDE.md` § Evals don't lie;
`evals/questions.yaml` batch-3 header.)

**Q20. Explain the strict-xfail pattern and why it beats deleting or skipping failing tests.**

**xfail** is test-suite jargon for "expected to fail": a test that
documents a known bug by asserting the bug is still present. Known
retrieval failures are encoded this way — with `strict=True` in Python, or
as inverted assertions labeled KNOWN FAILURE in TypeScript. Three
properties: the failure is documented in code, not in someone's memory;
the suite stays green, so *new* breakage remains visible; and — the
"strict" part — if a future change *fixes* the behavior, the expected
failure itself fails, demanding the marker be removed. Improvements are
forced to announce themselves. Both language suites carry the same two
known failures, so a fix must un-mark both together. (Source:
`tests/test_retrieval.py`; `packages/server-ts/test/retrieval.test.ts`.)

**Q21. There are two eval loops. Why, and what is each for?**

`evals/dev_check.py` runs the metric directly against the retriever in
under a second — for iteration while developing. The **promptfoo** harness
(an open-source evaluation framework for AI systems) runs the same metric
through the full provider layer and writes `reports/report.json` — the
committed record. The rule: measure on dev_check before any promptfoo run;
only promptfoo runs update the report. One metric, two costs, no confusion
about which number is authoritative. (Source: the `/eval-run` runbook;
`evals/dev_check.py` docstring.)

**Q22. Batch 4 added three questions for the new tools. Why do those questions still carry `expected_doc_ids`?**

Every question is scored by the deterministic retrieval provider today;
`expected_tool` / `expected_tool_args` are dormant grading criteria that
activate when an *agentic* provider — one where a real AI model chooses
which tools to call — runs the same set (gated on having a model API key).
Writing both into one question file keeps a single source of truth: the
same question is scored for retrieval now and for tool selection later.
All three passed retrieval on arrival (41/51 with no change to the failure
set). (Source: `evals/questions.yaml` batch-4 header.)

**Q22a. The 51 questions also chose the retriever. Does its 80% hold up on questions it was never tuned on? (2026-10-08)**

A score measured on the questions a design was chosen with tends to run
high. Choosing between designs rewards whatever happens to work on those
particular questions, including luck. So the 51 questions are a
**development set**. The fix is a **held-out set**: new questions that play
no part in any design choice and are scored once.

How the 118 held-out questions were made, with every rule committed to git
before any question existed (`evals/heldout/plan.md`):
1. **One question per section.** The server splits each corpus document
   into sections at its headings. All 120 sections with at least 30 words
   were used, so there was no sample to pick.
2. **Written blind.** A separate language-model agent saw only those
   sections. It wrote one question per section, the way a developer would
   ask it and in its own words, and skipped 2 sections that no developer
   would ask about: a license notice, and a block of example values. It
   never saw the retriever, its results or the 51 development questions.
3. **Answer key, labelled blind.** A second agent read all 7 documents and
   the shuffled questions, without knowing which section each came from,
   and listed every document that answers each one. 12 questions turned
   out to have more than one correct document.
4. **Frozen, then scored once.** The questions and the answer key were
   committed and pushed before the retriever saw any of them. Nothing was
   edited afterwards.

The rule, fixed in advance: the 80% "holds up" if it is shown to be within
10 points, that is, if the held-out score's **95% Wilson interval** sits
entirely at or above 70%. A Wilson interval is a standard range for a
proportion measured on a limited number of questions. Roughly, the true
accuracy on questions of this kind is very likely inside it.

Result: **102/118 = 86.4%, interval 79.1%–91.5%.** The bottom of the
interval clears 70%, so the 80% holds up. If anything, the held-out
estimate is higher, though the two ranges overlap. A correct document
appeared somewhere in the tool's five results for 117 of 118 questions.

Three checks, also fixed in advance, confirmed the measurement itself could
work and could fail:
- searching with each section's own text found the right document 118
  times out of 118;
- a random pick would be expected to score 16%;
- scoring each question with *another* question's answer scored 20%,
  no better than always answering the most common document (31%).

Where it misses: 8 of the 16 misses confuse the two documents that both
explain how to build llama.cpp with KleidiAI (the llama.cpp build guide
and Arm's patch guide). That is why the patch guide's questions score only
7/14. The misses are recorded, not fixed. Any fix will be tested on new
questions, because once this set is used to choose a design, it stops being
held out.

Limits:
- the questions were written by a language model from the documents, not
  asked by real developers;
- the writer and the labeller may share blind spots;
- documents with many sections weigh more, though a balanced average that
  counts each document once gives a similar 85%.

(Source: `evals/heldout/plan.md`; `evals/heldout/score.out`.)

---

## 6. Refutations on the record

**Q23. The original plan assumed a semantic retriever would beat lexical. What did measurement say?**

First, the terms: a **lexical** retriever matches words; a **semantic**
retriever uses **embeddings** — a technique that converts text into lists
of numbers so that "similar meaning" becomes "nearby points", the basis of
meaning-aware search. The hypothesis was refuted at feasible local-model
size. On the 48-question set: pure embeddings (model2vec `potion-base-8M`,
the strongest small embedding model that runs without the heavyweight
PyTorch library) scored **28/48** — worse than even the old
word-overlap scorer (34/48). A BM25+embedding hybrid tied pure BM25
(38/48) while adding a ~30 MB model download to every install. Decision:
two-level BM25, zero new dependencies; revisit only with a markedly
stronger model, decided by re-running the same A/B comparison. (Source:
`evals/reports/report.md` § The retriever A/B; `v0-decisions.md`
§ Retrieval.)

**Q24. Why did the corpus turn out to be lexical-friendly? Give the mechanism, not just the result.**

The vocabulary is dense, technical, and *discriminative at the token
level*: `qsi4cxp`, `GGML_CPU_KLEIDIAI`, `i8mm` are near-unique identifiers
whose IDF does exactly the work an embedding would approximate — and a
small embedding model actively blurs them (it maps rare technical tokens
into a crowded space where "similar-looking" beats "exactly right"). What
the old scorer's failures actually pointed at was word-frequency pathology
("mentions the topic densely" beating "canonically answers"), which BM25's
IDF and length normalization fix directly.

**Q25. The M2 handoff sketched a specific fix for the four "dilution" regressions. What was it, what happened, and why can't it work?**

Sketch: score each doc as max(whole-doc BM25, best dedicated-section
score), so a short answering section inside a long doc isn't diluted away.
Measured across 8 configurations, at the time with a script that copied the
search code (since 2026-10-04 the same comparison is
`evals/retrieval/ab_configs.py`, which runs the real search with different
settings and reproduces every result exactly):
**zero effect** in every combination. The reason is in the score data: the
docs that "steal" these queries contain their own dedicated sections
scoring at least as high as the wanted doc's section (Q15's worked
example: 2.832 vs 2.560, and the ordering holds under IDF-weighted
coverage too), so any max() scheme elects the same winner. A fix sketched
before measuring is just a hypothesis; this one didn't survive contact
with the data.

**Q26. The same A/B surfaced a second failure mechanism nobody had named. What is it?**

**Conversational-word IDF inflation.** Question phrasings contain words
that are *rare in a technical corpus* — "try", "want", "programming",
"combinations" — so BM25 assigns them high IDF (measured: 1.16–1.67, the
top rows of Q14's table), and a long doc matching one by accident
outscores the canonical doc. IDF cannot distinguish
rare-because-technical from rare-because-conversational; IDF-weighted
coverage *amplified* the problem (a pure win/loss trade), and the standard
English stopword list from NLTK (a widely used natural-language toolkit)
— which doesn't contain these words — scored strictly worse (36/48).
Fixing this requires understanding the *question*, not just its words,
which the "off-the-shelf retrieval only" guardrail rules out. Decision:
retriever unchanged, failures tracked.

**Q27. Why are these refutations presented as assets rather than embarrassments?**

Because the project's epistemics are its pitch. A measured refutation is
knowledge: it says precisely what was tried, what the data showed, and
under what conditions to look again ("markedly stronger model, same A/B").
The alternative — quietly not mentioning the idea, or shipping it untested
— is how systems accumulate superstition. The decision record turns "we
use BM25" from a default into a conclusion.

---

## 7. The kernel port, fully worked

**Q28. Decode `kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm` completely.**

First, orientation: a matrix multiplication computes dst = LHS × RHS,
where the **LHS** (left-hand side) holds the *activations* — the data
flowing through the model, new on every call — and the **RHS** (right-hand
side) holds the *weights* — the model's learned numbers, fixed once
training is done. Reading the name left to right, per the naming guide's
own dissection:

- `kai_` — KleidiAI namespace; `matmul_clamp` — matrix multiplication
  followed by a clamp (pinning results into a min/max range).
- `f32` — destination type: 32-bit floating point, the ordinary "full
  precision" format.
- `qai8dxp` — LHS: **q**uantized **a**symmetric signed **8**-bit
  (**i8**), **d**imension-wise (per-row) quantization (**dx**),
  **p**acked. The `4x8` after it is the packed layout block.
- `qsi4cxp` — RHS: **q**uantized **s**ymmetric signed **4**-bit (**i4**),
  per-**c**hannel quantization (**cx**), **p**acked; layout block `8x8`.
- `8x8x32` — an 8×8 block of the output computed per tile, with 32
  accumulation steps in the single innermost loop.
- `neon` — the SIMD technology used. (**SIMD** = single instruction,
  multiple data: one instruction operates on many numbers at once; NEON
  is Arm's SIMD instruction set.) `i8mm` — the Arm extension exploited
  (8-bit integer matrix multiply, feature flag FEAT_I8MM).

"**Packed**" (`p`) means the matrix must first be rearranged into a
cache-friendly layout by a matching pack micro-kernel — a `p` in any
buffer descriptor is a contract, and the matmul kernel's header names
which pack kernels it requires. (Source:
`corpus/kleidiai/matmul-qsi4cx-README.md` § Dissecting the filename;
`corpus/kleidiai/microkernel-names.md`.)

**Q29. Why does the port need exactly three micro-kernels, and what is the call order?**

Because both operand matrices are packed (`p`), and their lifecycles
differ:

1. `kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0` — **once, at load**: packs the
   int4 weights (parameters `lhs_zero_point=1`, `rhs_zero_point=8`, one
   f32 scale factor per output channel). Weights never change during
   inference, so this cost is amortized to zero.
2. `kai_lhs_quant_pack_qai8dxp_f32` — **before every matmul**:
   dynamically quantizes activations from f32 to int8 and packs them.
   Activations change per call, so this is part of the honest per-call
   cost and is timed.
3. `kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm` — the
   multiply, over the two packed buffers.

All packing parameters (named mr, nr, kr, sr) and packed-buffer sizes come
from the matmul kernel's `kai_get_*` helper functions — never hardcoded,
because they are properties of the chosen variant. Constraints: FEAT_I8MM
required; the shared dimension K must be a multiple of 8 (LHS pack) and
even (RHS pack); native int4 weights hold two values per byte, so the raw
RHS is n·(k/2) bytes. Build with `-march=armv8.2-a+dotprod+i8mm` (a
compiler flag saying which CPU features the generated code may use).
(Source: the qsi4cx guide, steps 1–9.)

**Q30. State the measured before/after, and read the table like an engineer.**

Shapes first: the benchmark multiplies an M×K input by a K×N weight
matrix, with N=K=4096. **M is how many rows you process at once** — M=1 is
*decode* (a language model generating one token at a time), M=32 a small
batch, M=256 a *prompt* chunk (digesting many tokens at once).
**GFLOP/s** = billions of floating-point operations per second, the
standard throughput measure. Measured on an Apple M5 Pro, single thread
(`demos/kernel-port/README.md`):

| shape | impl | median ms | GFLOP/s | weights MB | speedup |
|---|---|---|---|---|---|
| decode (M=1) | f32 baseline | 0.951 | 35.3 | 67.1 | 1.00× |
| decode (M=1) | KleidiAI int4 | 0.403 | 83.3 | 8.4 | **2.36×** |
| batch (M=32) | f32 baseline | 30.307 | 35.4 | 67.1 | 1.00× |
| batch (M=32) | KleidiAI int4 | 2.402 | 447.0 | 8.4 | **12.62×** |
| prompt (M=256) | f32 baseline | 245.575 | 35.0 | 67.1 | 1.00× |
| prompt (M=256) | KleidiAI int4 | 18.192 | 472.2 | 8.4 | **13.50×** |

Reading: the f32 baseline runs at a flat ~35 GFLOP/s across all three
shapes. This was first read as a *compute ceiling*: if M=1 were limited by
memory **bandwidth** (how fast data can stream from RAM) instead, that row
would fall *below* the M=32/256 figure, and it doesn't. That argument
turned out not to settle the question, because this f32 loop re-reads
every weight for every row, so a bandwidth limit would also give a flat
line. Q30b tested it directly, and the compute reading survived. At
M=32/256 the int4 kernel reuses each loaded weight across several input
rows and reaches 447–472 GFLOP/s, 12.6–13.5× the f32 loop. Q30b shows
that about half of that ratio is the reuse itself, which an f32 loop can
also have. At M=1 the win is real but smaller (2.36×), and the
explanation — **which has now been tested, see Q30a** — is the kernel's
shape: this is a **GEMM** variant (GEneral Matrix-Matrix multiply) whose
name declares an 8-row output tile (`8x8x32`) that M=1 cannot amortize.
That is exactly why dedicated **GEMV** variants (matrix-*vector*, built
for a single row) exist for decode: llama.cpp's integration selects a
different `…sme2_sdot` GEMV kernel for token generation than for prefill
(see the learn-arm doc's call stacks). The 8× weight-size reduction
(67.1 → 8.4 MB) remains a genuine end-to-end benefit (cache footprint,
keeping the model resident in memory); Q30b shows the f32 loop isn't
limited by memory bandwidth at this size.

**Q30a. That was an explanation, not a measurement. What happened when it was tested?**

The explanation implies a prediction, so it was run
(`demos/kernel-port/experiments/gemv-decode.cpp`, 2026-08-20). Stated
*before* measuring: a 1-row-tile GEMV variant should be ≥1.5× faster than
the GEMM incumbent at M=1 and should *lose* at M=32; refutation
condition: GEMV within ~10% of the GEMM variant at M=1. Measured (same
protocol as the benchmark — per-variant weight packing untimed,
activation quantization timed, correctness checked on every row):

| M | kernel | kind | total ms | vs f32 |
|---|---|---|---|---|
| 1 | `8x8x32_neon_i8mm` (incumbent) | GEMM | 0.398 | 2.45× |
| 1 | `1x8x32_neon_dotprod` | GEMV | **0.186** | **5.27×** |
| 32 | `8x8x32_neon_i8mm` | GEMM | **2.290** | **13.64×** |
| 32 | `1x8x32_neon_dotprod` | GEMV | 5.897 | 5.30× |

Both predictions confirmed: the GEMV variant is 2.14× faster at M=1, and
the crossover appears at M=32 (GEMV 2.6× slower) — the tile-amortization
signature exactly. The experiment also *refuted a sub-clause* of the
explanation as first written: it had blamed the per-call activation
quantization as a second factor, but the decomposition measures it at
0.001 ms of the 0.398 ms — 0.25%, negligible. One claimed mechanism
survived testing; the other didn't, and the text you are reading was
corrected accordingly. The residual gap between GEMV decode (181 GFLOP/s)
and GEMM prefill (469 GFLOP/s) is the engine: no i8mm GEMV variant exists
— i8mm's core instruction consumes two input rows at once, so 1-row
kernels fall back to the older dotprod feature's lower per-cycle
throughput, which is also why decode on SME2 hardware gets an `sdot`
kernel. Practical consequence for the demo and for real ports: variant
selection is shape-dependent — ship a GEMM kernel for prefill and a GEMV
kernel for decode, exactly as llama.cpp does.

**Q30b. Was the f32 baseline a fair "before"? (tested 2026-10-03)**

The worry came from an audit. The published f32 loop works through the
input one row at a time, and for each row it reads all 67 MB of weights
again, so 32 rows means 32 full passes. The int4 kernel instead computes
small blocks of rows together, so each weight it loads is **reused**
across several rows. That raised two questions. Both were written down
with their predictions and pass/fail rules, and committed to git before
anything ran (a **preregistration**: the commit's timestamp proves the
predictions came first).

*Question 1: is the flat ~35 GFLOP/s a compute limit or a memory limit?*
The test shrinks the weight matrix until it fits in the processor's
**cache** (a small, very fast memory on the chip itself), from 67 MB down
to 2 and 4 MB, changing nothing else. If memory bandwidth were the limit,
the small version would run at least 1.5× faster; if it were a compute
limit, it would stay within 15%. Measured with the Mac plugged in: 1.10×
faster (1.04–1.13 across five runs; an earlier run on battery gave 1.07×).
So the loop is **compute-limited**, and Q30's reading stands.

There's a refinement, though. The limit belongs to this loop, not to the
chip. Every multiply-add in it needs two numbers fetched (one input value,
one weight). When the same code shares each fetched weight across 4 rows,
it needs fewer fetches per multiply-add and runs at 74 GFLOP/s instead of
38. So ~35 GFLOP/s was never "the f32 number to beat" on this machine
(see Q32).

*Question 2: how much of the 12.6–13.5× is that reuse?* The test adds f32
loops that share each weight across 4 or 8 rows, then compares the int4
port with the faster of them. Measured: the port is 6.5× faster than the
reuse-matched loop at both M=32 and M=256, against 12.5–12.7× over the
original loop in the same runs. About half survives (0.52 at M=256, 0.51
at M=32). The plan's rule said that anything below 0.8 means the headline
must be restated, so the README now leads with 6.5× and gives 12.5–12.7×
second,
labelled as being against the loop without reuse.

*Also measured, with no prediction made in advance:* Apple's own math
library, **Accelerate**, which ships with macOS. Its f32 matrix multiply
(`sgemm`) on one thread reaches 1,497 GFLOP/s at M=256. That is about 3×
the int4 port and 20× the reuse-matched f32 loop, and it points to the
M5 Pro's separate matrix unit (**SME**, Arm's Scalable Matrix Extension)
rather than the ordinary vector units all the other code here uses.
Accelerate beats the int4 port 1.5× at M=32 and 3.2× at M=256; the int4
port wins at decode (M=1, 1.4×) and keeps its 8× smaller weights.

This doesn't contradict the port; it shows the comparison spans two
different pieces of hardware. KleidiAI also ships kernels for the SME
matrix unit (llama.cpp uses them, see Q30), so comparing one of those
with Accelerate is the obvious next experiment.

*Checks that the run was sound:*
- The published numbers reproduced within ±10%: f32 at 38 GFLOP/s
  against 35, and int4 at 2.32×, 12.52× and 12.71×.
- The reuse loops at M=1, where there is nothing to reuse, timed at
  exactly the published loop's speed.
- Every output was checked against the f32 result.
- One deviation is on record: the first run used battery power, not
  plugged in as planned. The plan declared a plugged-in replication in
  advance, to be reported whatever it showed and to govern if the two
  disagreed. It ran on 2026-10-04 and reached the same verdict on every
  question; the numbers in this answer are from it.

(Source: `demos/kernel-port/experiments/baseline-fairness.md`;
`demos/kernel-port/results/2026-10-04-1638-baseline-fairness/summary.md`;
the battery run: `demos/kernel-port/results/2026-10-03-1621-baseline-fairness/summary.md`.)

**Q31. The port's rel-RMSE against f32 is 6.7×10⁻². Derive why that is exactly the expected value, not an error.**

**RMSE** is root-mean-square error — a standard "typical size of the
error" measure; *relative* RMSE divides it by the typical size of the true
values, giving a percentage-like ratio. Setup: test weights drawn
uniformly from [−1, 1]; per-channel symmetric int4 quantization with the
recipe's scale, so the quantization **step** is s = range/15 (16 levels
from −8 to +7 span 15 steps).

- Rounding to the nearest level makes each weight's error effectively a
  uniform random draw from [−s/2, s/2], whose standard deviation (typical
  size) is **s/√12** — a standard result for uniform distributions.
- The weights themselves are uniform over the whole range, so their
  standard deviation is **range/√12**.
- Each output of the matrix multiply is a sum over K = 4096 independent
  terms; the error sum and the signal sum both grow the same way (with √K
  and with the activation values), so the *ratio* survives the dot
  product.

Therefore:

    rel RMSE = (s/√12) / (range/√12) = s / range = 1/15 ≈ 0.0667

The measured 6.7×10⁻² *is* 1/15 to the precision shown. Cross-check the
other error source: the activations' dynamic int8 quantization contributes
~1/255 ≈ 0.004 by the same argument; combining independent errors as the
square root of the sum of squares gives √((1/15)² + (1/255)²) ≈ 0.0668 —
indistinguishable. A *wrong* port (bad nibble packing, swapped scales)
produces errors of order 100%, so the check discriminates sharply between
"quantized" and "broken". Caveat recorded in the README: real language
models' weights aren't uniform, so this exact value is a property of the
test data — and the initial "~1e-2" guess in the harness was itself
corrected by this derivation when the measurement disagreed.

**Q32. Why was the f32 baseline compiled with `-ffast-math`, and why is that a fairness argument rather than a compromise?**

A quirk of floating-point arithmetic: addition isn't perfectly
associative — (a+b)+c can differ in the last decimal places from a+(b+c) —
so by default the compiler must keep sums in written order, which prevents
it from using SIMD to add eight numbers at once. `-ffast-math` grants
permission to reorder, letting the compiler **vectorize** the loop (turn
it into SIMD form). Without it, the "baseline" would be
one-number-at-a-time scalar code — a strawman that flatters the port.
Inference engines routinely enable fast-math or hand-vectorize. But
vectorizing makes the loop competent, not the strongest f32 baseline:
sharing each weight across rows doubles its speed, and Apple's Accelerate
library is faster still (Q30b). The before/after is only meaningful if the
"before" is defensible, which is why the headline now reports the stronger
baselines too. (Source: `demos/kernel-port/build.sh` header
comment.)

**Q33. The port already exists in the repo. Doesn't that make the recorded "agent ports it live" demo theater?**

It would, if the answer key were anywhere the agent can look during
recording. Inside this repository it is in many places: the rehearsal port
in `src/`, the demo README's recipe, the experiments (which reuse the
port's kernels and quantization recipe), this workbook, the QA set's
curator notes, and the repository's **git history** (the stored record of
every past version, which `git log` or `git diff` will print on request).
Hiding files in place can't remove the last of these: after deleting the
port, a routine `git status` or `git diff` shows exactly what was deleted.

So the recording happens somewhere else. `demo-reset.sh workspace <dir>`
builds a fresh folder outside the repository containing only the baseline:
the f32 kernel, a harness and build script that know nothing of the port,
and Arm's own KleidiAI source checkout (the library being ported to, which
any developer would have). It becomes a new git repository whose single
commit is that baseline, so there is no history to find. It registers the
MCP server for the agent and then searches every file outside the KleidiAI
checkout for the port's identifiers, refusing to finish if any survive.
The agent can still reach this repository by path, but every file it
reads appears in the recorded transcript. The integrity claim is
"re-derived without the answer key in reach", and the transcript is where
a reader checks it.

The rehearsal's existence is disclosed in the README; the claim is
"re-derived", not "never done before". The rehearsal is what de-risks the
recording: the destination is known to be reachable, so a failed session
means process, not physics. (Source: `demos/kernel-port/demo-reset.sh`;
`recording-plan.md`.)

---

## 8. Two servers, one contract

**Q34. The repo claims "identical tool surface across SDKs." Byte-identical schemas are impossible — pydantic and zod emit different JSON. How is the claim made honest?**

(An **SDK** is a software development kit — here, the official MCP
libraries for Python and TypeScript, which this project uses to build two
parallel servers.) The claim is made honest by defining what the contract
*is*: tool names, parameter names, types, required flags, and defaults.
Both live servers are dumped through a normalizer that strips generator
cosmetics (pydantic's decorative `title` fields, envelope differences),
and CI compares the results. "Identical surface" is then a checkable
statement about what a client can rely on, not an accident of library
versions. (Source: `distribution/schema-sync/dump_contract.py`
docstring.)

**Q35. The parity gate has three checks, not one. Name them and what each would catch.**

1. **Contract** (normalized schema comparison) — catches a renamed
   parameter, a changed default, a type drift: anything that breaks a
   client written against the other server.
2. **Retrieval top-1 on all 51 eval questions** — catches *behavioral*
   drift between the two BM25 implementations: a tokenizer edge case, a
   different tie-break, a floating-point ordering difference.
3. **Pattern/planner content** (full JSON of the catalog, every pattern,
   and canonical planner outputs) — catches content drift; it's held
   trivially true by both servers reading one `patterns.yaml`.

All three run in CI's `schema-sync` job on every change. (Source:
`distribution/schema-sync/check.sh`.)

**Q36. Check 2 is the boldest — it demands exact agreement of float-ranked results across languages. Why does that work?**

Both languages do arithmetic in the same standard 64-bit floating-point
format (IEEE-754 double precision), and the TypeScript port mirrors every
constant, formula, and — crucially — the tie-break order (Python's sort
on the triple (doc score, chunk score, index), descending, is reproduced
as an explicit three-key comparison). The one theoretical hazard is
summation order: float addition isn't associative, and the two languages
may sum a document's matched terms in different orders, producing
differences around the fifteenth decimal place — but those only matter if
two *different documents* score that close, which never occurs on this
corpus. The gate measured the question rather than assuming: 51/51
agreement on the first run. If a future corpus produces such a near-tie,
the gate will say so loudly, which is the point. (Source:
`packages/server-ts/src/corpus.ts` header and sort comment.)

**Q37. Within hours, the parity gate proved its worth on a real event. What happened?**

**Dependabot** — GitHub's robot that proposes dependency updates as pull
requests (**PRs**: proposed changes that run through CI before merging) —
proposed upgrading zod from version 3 to 4: a *major* version change of
the exact library that generates the TypeScript tool schemas. The
schema-sync job ran the full parity suite against the proposal and
passed: mechanical proof that the tool contract survived a major upgrade
of the schema generator. That's the difference between "we believe the
schemas match" and "a machine checks it on every change" — the gate
converted a scary upgrade into a routine merge.

**Q38. The two servers sit on different SDK majors — Python on mcp 2.x, TypeScript on SDK 1.x. Why is that correct rather than sloppy?**

(Version numbers like 2.1.3 follow a convention where the first number —
the **major** — changes only for breaking changes.) Each server targets
its SDK's *current* major: the Python SDK's 2.0 restructuring shipped; the
TypeScript SDK's hasn't. The alternative — holding Python back for
cosmetic symmetry — would publish v1.0 against a superseded major. The
parity target is the *contract* (Q34), which is SDK-independent; declaring
each dependency's supported major explicitly (`mcp>=2.0,<3`, `^1.30.0`)
is what prevents the next restructuring from arriving as a surprise.
(Source: `pyproject.toml` dependency comment; `architecture.md` § Server.)

---

## 9. Packaging and distribution

**Q39. The server worked perfectly in every test, yet a `pip install` of the wheel would have shipped a broken product. What was the bug?**

(`pip` is Python's installer; a **wheel** is Python's ready-to-install
package format.) The server locates its corpus by walking up the folder
tree from its own code until it finds `corpus/manifest.yaml` — which
exists in a repository checkout but not above the system folder where
installed packages live. Every test ran inside the checkout, so nothing
failed locally; the failure mode existed only for the installed artifact.
It was caught by reasoning about the deployment environment during the
TypeScript port, then *proved* by building the wheel, installing it into a
scratch environment, and running the server from a bare temp directory —
first demonstrating the failure, then the fix.

**Q40. Why not just tell the build tool to include `../../corpus` in the wheel? Work through the monorepo trap.**

(A **monorepo** is one repository containing several packages — here, the
Python and TypeScript servers live in subfolders, and the corpus lives
above them. An **sdist** is Python's *source* package format: when someone
installs from an sdist, the wheel gets built on *their* machine from the
sdist's contents.) The build tool's "force-include ../../corpus" feature
resolves that path at build time relative to the package folder — and
inside an unpacked sdist, there *is* no `../../corpus`, so the path
silently doesn't exist exactly when it matters. The robust design: a
release-time staging step (`distribution/prepare_corpus.py prepare`)
copies the corpus *inside* the package folder before building, so both
sdist and wheel contain it by ordinary inclusion; `clean` removes the
staged copies, which are git-ignored so the committed corpus remains the
single source of truth. At runtime the server looks in order:
`KLEIDIAI_CORPUS_DIR` environment variable → repository walk-up → the
packaged copy. The manifest ships with the copy — provenance travels.

**Q41. How was the fix verified to the standard the repo sets elsewhere?**

The only test that counts for packaging is the installed artifact in a
clean environment: the wheel was installed into a fresh, isolated Python
environment, the npm package archive was unpacked standalone, and each
server was driven by a real MCP client over stdio *from a working
directory outside the repository* — all three tools listed, search
returning cited results, patterns resolving. (The npm side gets the
staging for free via its standard pre/post-packaging hooks.)

**Q42. What does the MCP registry entry add beyond PyPI/npm?**

(PyPI and npm are the standard public package indexes for Python and
JavaScript.) Discovery: registry.modelcontextprotocol.io is the official
index that MCP clients browse to find servers. `distribution/registry.json`
names the server, its repository, and its package coordinates; the
`mcp-publisher` tool submits it at M4. PyPI/npm distribute the artifact;
the registry is how an agent user finds out it exists. (Source:
`v0-decisions.md` § Distribution.)

---

## 10. Engineering-practice lessons (all from one day, all on the record)

**Q43. The first-ever CI run failed on code that had been "passing" for weeks. Reconstruct the full causal chain.**

The CI workflow file existed since July, but the repository had no remote
copy on GitHub until 2026-08-20 — no uploads, so the checks never ran. The
first upload triggered the first run, which installed a *floating* (not
version-locked) toolchain and got a newer release of **ruff** — a linter,
a tool that flags error-prone or unidiomatic code — whose default rule set
now flagged a line committed weeks earlier. Meanwhile **mypy** — a type
checker, which verifies the code's type declarations are consistent — had
never actually been executed, and failed on two long-standing gaps. Two
latent debts, invisible because the enforcement had never run. Fixes: lock
the toolchain to exact versions so CI and the local environment enforce
identical rules *by construction*, and pay off the type debt. Lesson: an
unexercised quality gate is a liability that converts to a surprise
precisely when you first rely on it.

**Q44. The same day, an unbounded runtime dependency nearly shipped a server that couldn't import. Details, and the general rule.**

The declared requirement was `mcp>=1.0` — "version 1.0 or *anything*
newer", with no upper limit. The MCP Python SDK then released 2.0.0, a
restructuring that removed the module this server imported — so any fresh
install grabbed 2.0.0 and failed at startup, while the development
environment sat safely on 1.28.1. CI's fresh install exposed it.
Immediate fix: cap the requirement below 2. Durable fix, done the same
day: migrate to 2.x deliberately (three small renames), verify the
generated schemas were identical, and re-cap as `>=2.0,<3`. General rule:
runtime dependencies are bounded to the major version the code actually
targets; major upgrades are migrations you choose, not something the
installer decides for you.

**Q45. Contrast the fates of the eight Dependabot PRs from the first sweep, and what the outcome demonstrates.**

Six merged, all adjudicated by the automated gates rather than by mood:
three GitHub-Actions majors, a mypy patch release, the Node type
definitions (@types/node 26), and zod 4 (Q37 — the parity gate proving
the contract unchanged). Two failed CI honestly and were *held with
comments* instead of merged-and-hoped: TypeScript 7 (real compile breaks)
and ruff 0.16 (a new default rule firing). Both were then taken
deliberately the same evening: the TypeScript-7 "migration" turned out to
be one configuration line (the new compiler stopped auto-loading type
definitions), and ruff 0.16's one complaint was evaluated on merits and
overridden with a documented waiver (a 28-element list literal reads
worse than the one-line idiom it would replace). The demonstration: with
locked versions plus real gates, dependency churn becomes a stream of
deliberate, reviewable decisions — neither auto-merged risk nor frozen
rot.

**Q46. When ruff demanded a change and the project refused, what made that refusal legitimate rather than gate-dodging?**

Three properties: the override is *narrow* (a one-line `# noqa` marker —
lint-speak for "skip this one rule on this one line" — with the rule
enabled everywhere else), *reasoned in place* (a comment states why the
idiom is preferred and that the list changes rarely), and *visible* (the
commit message argues the case). A lint rule is a default, not a law; the
failure mode to avoid is silent blanket disabling, not disagreement.

**Q47. Why does this repo lock dev tools to exact versions but bound runtime deps by major? The two policies look inconsistent.**

They optimize different risks. Development tools (ruff, mypy) are
*judges*: two judges applying different rulebooks to the same code produce
spurious verdicts, so the local environment and CI must match exactly —
locked versions, updated via Dependabot PRs where the version bump is
itself the reviewed change. Runtime dependencies (mcp, yaml, zod) are
*load-bearing libraries* for downstream installers: exact locks would
fight users' dependency resolvers and block security patches, so they get
the widest range the code actually supports — the targeted major.

---

## 11. What remains, and why it's human-gated

**Q48. Everything left before v1.0 requires a human. Enumerate, and say why each can't be delegated.**

1. **Record the M3 demo** (the `/demo-record` runbook walks it). The
   artifact is a screen recording of a live agent session — only a human
   can capture the screen and, more importantly, vouch that the committed
   transcript is the genuine one. The repo's integrity story would be
   worth little if its flagship evidence were synthesized by the assistant
   that built the repo.
2. **Publish** (the `/release` runbook walks it): the PyPI upload, the
   GitHub release, the MCP registry submission, flipping the repository
   public. All outward-facing and hard to take back; each step gets
   explicit human confirmation by design.
3. **The agentic eval tranche** — the dormant tool-choice grading in
   `questions.yaml` activates when a model API key (paid access to an AI
   model, needed for an agent to drive the tools during evaluation) exists
   in the environment; that's a resource decision, not a code change.

**Q49. If you could hand a reviewer only one file to judge this project by, which one, and what's the argument?**

`evals/reports/report.md`. It contains the score history including the
dips, two refutation records with their mechanisms, the categorized
failure table, and the decision rationale for the retriever — the whole
epistemic character of the project in one document. The README says what
the project claims; the report shows how the project *knows*.

---

*Written 2026-08-20; renamed from quiz.md and rewritten in plain language
the same day. When the facts change — new eval runs, the recorded demo,
the publishes — update the affected answers or add a dated section; don't
let this workbook join the things it would then be lying about.*
