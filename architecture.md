# Architecture

How the pieces fit, and why each boundary sits where it does. Decision
rationale lives in `v0-decisions.md`; this file is the map.

```
corpus/manifest.yaml ──── the contract ────┐
        │                                  │
        ▼                                  ▼
corpus/*.md ──▶ corpus.py ──▶ server.py ──▶ MCP client (stdio)
   (bytes as    (chunking +    (FastMCP,
    fetched)     two-level      tool schema =
                 BM25)          cross-SDK contract)
        ▲              ▲
        │              │
  test_provenance   evals/ (promptfoo + dev_check over questions.yaml,
  (SHA-256 gate)           reports committed) ──▶ demos/kernel-port
                                                  (the eval's e2e question,
                                                   made real on hardware)
```

## Corpus: the moat

`corpus/` holds byte-identical copies of real upstream docs. The manifest
(`corpus/manifest.yaml`) is the single contract: an entry records url,
pinned commit, fetch timestamp, SHA-256, license, and a one-line description
of what the doc canonically answers. Only manifest-listed, non-removed
entries are indexed — an undocumented file under `corpus/` is a test failure
(`packages/server-py/tests/test_provenance.py`), and an in-tree edit to a
fetched doc breaks its SHA-256 check. Sources that disappear upstream keep
their entry with a `removed_at:` note. This is what "no fabricated content"
means mechanically.

## Retrieval: deliberately boring

`corpus.py` splits docs at markdown headings and runs two-level Okapi BM25:
doc-level scoring (coverage-scaled) picks which docs canonically answer;
chunk-level scoring (headings weighted 3×) orders passages within them, ≤2
per doc. Standard constants, no tuning, no model download, no API key.

The boringness is load-bearing and evidence-backed: the differentiator is
corpus + evals, not retrieval cleverness, and every attempt to be cleverer is
on the record as a measured refutation — static embeddings scored 28/48 vs
BM25's 38/48, the hybrid tied while adding a dependency, and the three
dilution-fix mechanisms (section rescue, IDF-weighted coverage, larger
stopword list) all failed to beat baseline (`evals/reports/report.md`,
`evals/retrieval/ab_dilution.py`). Known residual failures are pinned by
strict-xfail tests that demand un-marking the day something fixes them.

## Server: a thin shim on purpose — twice

`server.py` (and its sibling `packages/server-ts/src/server.ts`) is a thin
shim: one lazy corpus load and tools that return doc-cited results. All
intelligence lives in the corpus, the retriever, and the pattern catalog,
which is what makes a faithful two-language port cheap. Parity is enforced
three ways in CI's schema-sync job (`distribution/schema-sync/check.sh`):
normalized tool contracts diff clean, both retrievers return the same top-1
doc on every eval question, and pattern/planner content is identical
(single-sourced from one patterns.yaml). `tests/test_server.py` additionally
asserts the schema explicitly so drift is a deliberate act, not an accident.
The two servers deliberately sit on their SDKs' current majors (Python: mcp
2.x; TypeScript: SDK 1.x) — the contract is the parity target, not the SDK
version.

## Evals: the decision-maker

`evals/questions.yaml` holds 51 development questions (also used to choose
the retriever, so not held out; a held-out set is planned) with expected doc
ids,
including deliberately HARD ones and tool-use/e2e tranches awaiting an
agentic provider. Two loops share one metric (top-1 doc):

- `evals/dev_check.py` — seconds; for iteration.
- promptfoo (`evals/promptfooconfig.yaml`) — the committed record;
  `evals/reports/` is regenerated and committed on every corpus or server
  change.

Rules that keep the numbers honest: questions are never tuned to flatter the
server; ground truth changes only under the † widening policy in dedicated
commits; regressions get recorded and categorized, not masked; retriever
changes require a measured A/B. The `/eval-run` command encodes the
workflow.

## Demos: the eval made visceral

`demos/kernel-port/` is the e2e eval question (`e2e-port-kernel-int4`) run on
real hardware: an f32 matmul ported to KleidiAI's qai8dxp/qsi4cxp int4
micro-kernels, judged by compile + quantization-theory RMSE + speedup. The
KleidiAI checkout is pinned to the same commit the corpus docs were fetched
at, so the code the agent reads matches the docs it retrieves. Rehearsed
numbers and methodology live in the demo README; the recorded session (M3
deliverable) re-derives the port through the MCP server.

## What talks to what — and what doesn't

- The server never fetches at runtime; it reads only the committed corpus.
- The evals exercise the server as an external system-under-test (stdio),
  same as any MCP client.
- The demo consumes the server the way an end user's agent would; it has no
  private hooks.
- Nothing here integrates with other portfolio projects by design
  (`v0-decisions.md`, companion-repo rule).
