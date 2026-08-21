# v1 Locked Decisions — mcp-server-kleidiai

Decisions locked 2026-05-28 during the initial planning session. Each entry lists the reasoning so future work can judge whether the rationale still holds.

## Wedge: llama.cpp + KleidiAI

The MCP server anchors specifically on llama.cpp's KleidiAI integration — local LLM inference on Arm CPUs with KleidiAI as the matmul backend.

**Why:** Hottest agentic-AI framing in 2026. M-series Mac, Snapdragon X, and Graviton users run llama.cpp daily. KleidiAI as a whole is too broad to be "best in genre" on day one; picking a sub-wedge sharpens corpus, evals, and the killer demo. ExecuTorch (v1.5) and KleidiAI core C kernels (v2) are additive extensions, not redesigns.

## Stack: Python first, TypeScript fast-follow

Python MCP server ships to PyPI first; TypeScript port follows within weeks and ships to npm.

**Why:** Python is the stronger day-one bet — the MCP Python SDK is mature and it's the fastest path to a working server + eval loop here — and the fast-follow TS port still earns the "across different SDKs" claim without doubling day-one work, both maintained off a single tool-schema source of truth.

> **Correction (2026-07-14):** an earlier version of this rationale claimed Promptfoo iteration is "materially faster in Python (Promptfoo + `mcp-agent-provider` are Python-native)." That is factually wrong — Promptfoo is a Node/npm CLI. It exercises the MCP server as an external system-under-test *regardless of the server's language*, so it does not favor Python. The Python-first decision still stands, but on the SDK-maturity / velocity grounds above, not on Promptfoo.

## Eval framework: Promptfoo + mcp-agent-provider

Evals run on Promptfoo's MCP Provider (server-as-system-under-test) and `mcp-agent-provider` (for agentic tool-use scoring).

**Why:** No other eval framework has first-class MCP support as of May 2026. Promptfoo's `mcp-agent-provider` was purpose-built for this shape of test. Inspect-AI is a viable alternative but lacks the MCP-specific provider tooling.

## Distribution: PyPI + npm + MCP registry

Published to PyPI, npm (after TS port), and registry.modelcontextprotocol.io via the `mcp-publisher` CLI.

**Why:** All three are the canonical distribution surfaces in mid-2026. The MCP registry (launched Sept 8, 2025; ~2,000 servers within months) is the official discovery channel. PyPI and npm are the SDK-level distributions. The "publish/package/maintain across different SDKs and MCP registries" claim only holds if all three channels are live.

## Corpus storage: committed, not fetched-on-demand

Fetched docs are committed in-tree under `corpus/`. `corpus/manifest.yaml` records source URL, fetch date, and SHA-256 for each entry.

**Why:** Self-contained repo for reviewers; offline-reproducible evals; protects against source-URL rot. Costs git size — acceptable for the portfolio context where reviewability beats lean cloning.

## Killer demo (M3): kernel port to KleidiAI int4

The headline demo: an agent uses the MCP server to port a real matmul kernel to KleidiAI int4, with a before/after benchmark on M-series Mac. Recorded as video + transcript + notebook in `demos/kernel-port/`.

**Why:** Visceral perf delta beats a build-walkthrough demo. The agent's role is specific and verifiable (the patch either applies and benchmarks better, or it doesn't). Tight enough scope to ship in one week.

## Repo layout: monorepo (packages/, corpus/, evals/, demos/, distribution/)

Single repo containing Python server, TypeScript server, shared corpus, evals, demos, and distribution tooling.

**Why:** Cross-SDK schema validation requires both servers in one place. Eval reports reference a single corpus. Demos pull from a single eval question set. Splitting these into separate repos would mean cross-repo CI complexity for no review benefit.

## Companion-repo rule: no Bridget integration

Bridget Washington (the companion iOS portfolio piece, a separate repo) is deliberately not used as a demo, dependency, or integration target here.

**Why:** Forcing coherence between an iOS app and an Arm-MCP knowledge server requires reintroducing on-device ML to Bridget, which expands Bridget's locked v0 scope at App Store submission time. The narrative coherence ("ship on Arm + build for Arm developers") lives on the GitHub profile, not in code.

## License: Apache-2.0 (finalized 2026-08-20)

Apache-2.0, committed as `LICENSE` (canonical text) with third-party
attribution in `NOTICE` (corpus docs retain their own licenses per the
manifest; the learn-arm doc is CC-BY-SA-4.0 share-alike).

**Why:** Apache-2.0 matches `ARM-software/kleidiai` upstream. Apache is also the dominant license for AI/ML tooling (Anthropic SDKs, most Arm OSS). Originally provisional; finalized ahead of M4 as part of the distribution machinery.

## Retrieval: two-level BM25, no embeddings (decided 2026-08-05)

Retrieval is doc-level Okapi BM25 (coverage-scaled) for doc ranking plus
chunk-level BM25 for passage ordering. No embedding model, no new runtime
dependency.

**Why:** The M2 eval was built to prove whether a semantic retriever helps —
it answered no, at feasible local-model size. Measured A/B on the 48-question
set (full table in `evals/reports/report.md`): pure static embeddings
(model2vec potion-base-8M, the strongest torch-free local option) scored
28/48 — worse than the original token-overlap scorer (34/48) — and a
BM25+embedding hybrid merely tied pure-lexical BM25 (38/48) while adding a
~30MB model download to every install. The corpus vocabulary is dense and
technical; the discriminative signal is lexical, and IDF + doc-level evidence
aggregation captured the systematic weakness categories the eval documented.
Consistent with the CLAUDE.md guardrail: off-the-shelf retrieval, the
differentiator is corpus + evals. **Revisit** only with a markedly stronger
embedding model (API key or larger local model), decided by re-running the
same A/B — never by assumption.

## Milestones (6-week v1 target)

- **M1 (weeks 1–2)** — Python MCP server skeleton; corpus ingestion pipeline; first tool (`search_kleidiai_docs`); 10 hand-curated QA pairs as a smoke test.
- **M2 (week 3)** — Promptfoo eval harness; 50-question held-out QA set; first scored report committed under `evals/reports/`.
- **M3 (week 4)** — Killer demo recorded: agent ports a real matmul kernel to KleidiAI int4; benchmark video + notebook + transcript in `demos/kernel-port/`.
- **M4 (week 5)** — PyPI publish; MCP registry submission via `mcp-publisher`; finalize `LICENSE`; install docs in README.
- **M5 (week 6)** — TypeScript port; shared-schema CI; npm publish.

## Niche claim narrowed: "first" -> "only knowledge server found" (2026-08-21)

All public copies of "the first MCP server in this niche" are replaced with a
dated, hedged, checkable claim: as of August 2026, the only MCP server found
that serves KleidiAI knowledge — adjacent servers benchmark it, none serve
the documentation.

**Why:** Verification ahead of circulating the public repo found the niche no
longer empty. `sirmos/arm-pulse` (public 2026-06-13) is a KleidiAI-powered
benchmark suite + MCP server; `CisnerosCodes/arm-migrate-mcp` (2026-07-15) is
a migration harness with measured KleidiAI benchmarks; Arm ships an official
MCP server whose `knowledge_base_search` covers Arm learning resources
generally. None serve a curated KleidiAI corpus, so the narrowed claim holds
— but "first" cannot be proven from public history (this project's public
repo dates from 2026-08-20, after both community servers) and a primacy claim
invites refutation where a substance claim invites confirmation. Checked
2026-08-21: MCP registry search ("kleidiai": zero entries), GitHub repo
search, web search. Same discipline as retrieval: claims are decided by
looking, recorded with their evidence, and revisited by re-running the check.
