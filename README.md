# mcp-server-kleidiai

[![CI](https://github.com/PeterJemley/mcp-server-kleidiai/actions/workflows/ci.yaml/badge.svg)](https://github.com/PeterJemley/mcp-server-kleidiai/actions/workflows/ci.yaml)

An MCP server that gives AI agents structured access to KleidiAI + llama.cpp
Arm optimization expertise — a curated, provenance-verified corpus behind
queryable tools, with the retrieval quality measured and committed.

As of August 2026, the only MCP server we've found that serves KleidiAI
*knowledge* — adjacent MCP servers in this space run benchmarks; none serve
the documentation (checked 2026-08-21 against the MCP registry, GitHub, and
web search).

## Why

KleidiAI is Arm's library of optimized micro-kernels for AI workloads on Arm
CPUs. llama.cpp uses KleidiAI as its matmul backend on Arm (enabled via
`GGML_CPU_KLEIDIAI=ON`), so every llama.cpp user on an M-series Mac,
Snapdragon X, or Graviton instance is already running it implicitly.

No MCP server today lets an AI agent reason about KleidiAI + llama.cpp Arm
optimization. The knowledge lives across `ARM-software/kleidiai`,
`Arm-Examples/ML-examples`, `ggml-org/llama.cpp`, learn.arm.com learning
paths, and Arm engineering blogs. This server consolidates that surface into
tools an agent can call — every answer citing the real source doc, never a
paraphrase.

## Tools

| Tool | What it does |
|---|---|
| `search_kleidiai_docs(query, limit=5)` | Two-level BM25 search over the corpus; returns passages with `doc_id`, source `url`, `heading`, `snippet`, and relevance score. |

The tool surface is served by both implementations — Python
(`packages/server-py`, PyPI at M4) and TypeScript (`packages/server-ts`, npm
at M5) — and their parity is enforced in CI: identical normalized tool
contracts, identical retrieval top-1 on every eval question, and identical
pattern/planner content (`distribution/schema-sync/check.sh`).

## Measured, honestly

Retrieval accuracy is scored on a 51-question held-out QA set (top-1 doc
metric) and the reports are committed — reviewers see scores without running
anything. Current: **41/51 (80%)** overall (2026-08-20 report), with the 10
remaining failures grouped by mechanism and tracked by strict-xfail tests. Retriever decisions
are made by measured A/B, including two refutations on the record (semantic
embeddings at feasible local size; three dilution-fix mechanisms). See
[`evals/reports/report.md`](./evals/reports/report.md).

## Kernel-port demo (M3, in progress)

Ports an f32 matmul to KleidiAI int4 (`qai8dxp`/`qsi4cxp`, i8mm variant).
The port and benchmark are committed and reproducible from
[`demos/kernel-port/`](./demos/kernel-port/): on an Apple M5 Pro,
single-threaded, **2.4× (decode) to 13.5× (prompt)** over a vectorized f32
baseline, weights 67 MB → 8.4 MB, quantization error matching int4 theory to
two digits. Those numbers are from the hand-written rehearsal. The recorded
session — an agent re-deriving the port using this server's tools — is
pending and will be published here when it exists; until then, no
agent-driven claim attaches to these numbers.

## Run from source

Not yet on PyPI (that's M4). Until then:

```sh
cd packages/server-py
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests -q   # 15 passed, 2 xfailed expected
```

MCP client configuration (stdio):

```json
{
  "mcpServers": {
    "kleidiai": {
      "command": "/path/to/mcp-server-kleidiai/packages/server-py/.venv/bin/python",
      "args": ["-m", "mcp_server_kleidiai"]
    }
  }
}
```

The server locates `corpus/manifest.yaml` by walking up from the package, or
via `KLEIDIAI_CORPUS_DIR`.

## Layout

```
packages/        Python + TypeScript MCP servers (parity enforced in CI)
corpus/          Curated committed docs — every entry provenance-verified
                 (url, commit, fetch date, SHA-256, license) in manifest.yaml
evals/           Promptfoo harness + 51-question QA set + committed reports
demos/           kernel-port: f32 → KleidiAI int4 with before/after benchmark
distribution/    Publish tooling + cross-SDK parity checks (schema-sync)
```

`architecture.md` explains how the pieces fit; `v0-decisions.md` records the
locked design decisions and their reasoning; `about.md` is the plain-language
tour; `docs/evidence-discipline.md` maps the evidence-handling principles to
where the repo enforces them; `docs/msk-workbook.md` is the fully worked Q&A.

## Roadmap

- **v1.0** — Python server, eval harness, kernel-port demo, PyPI + MCP
  registry publish
- **v1.1** — TypeScript port, npm publish, shared-schema CI
- **v1.5** — ExecuTorch + KleidiAI corpus extension
- **v2** — KleidiAI core C kernels corpus extension

## License

Apache-2.0 (matching upstream ARM-software/kleidiai) — see `LICENSE`.
Corpus documents retain their original licenses, recorded per entry in
`corpus/manifest.yaml`; the learn-arm doc is CC-BY-SA-4.0 (share-alike).
Third-party attribution in `NOTICE`.
