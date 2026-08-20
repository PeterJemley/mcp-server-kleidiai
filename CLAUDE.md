# mcp-server-kleidiai — Project Context

mcp-server-kleidiai is **an MCP server that gives AI agents structured access to KleidiAI + llama.cpp Arm optimization expertise**. It is the first MCP server in this niche — Arm has intro-level MCP tutorials but nothing that exposes KleidiAI knowledge as a queryable tool surface.

This is a portfolio piece demonstrating MCP knowledge bases, evaluation frameworks, and agentic AI workflows — in particular, the discipline of building a queryable evidence system where every claim carries its provenance and the quality numbers are measured and published rather than asserted.

Locked v1 decisions live in `v0-decisions.md` — read alongside this file.

A companion iOS repo (Bridget Washington, a separate local repo) exists as a separate Apple-Silicon/Arm portfolio piece. The two coexist on the GitHub profile as independent products. Bridget is deliberately **not** used as a demo here, and this server does not graft onto Bridget. The narrative coherence ("ship on Arm + build for Arm developers") lives on the GitHub profile, not in code.

## v1 Scope (locked 2026-05-28)

The minimum publishable cut:

1. **Python MCP server** indexing a curated corpus of KleidiAI + llama.cpp Arm optimization docs. At minimum: a `search_kleidiai_docs` retrieval tool, a `get_kleidiai_pattern` lookup tool, and one task-shaped tool wired to the killer demo.
2. **Promptfoo eval harness** scoring retrieval accuracy + tool-use correctness on a held-out QA set. Reports committed to `evals/reports/`.
3. **Killer demo**: an agent uses the server to port a real matmul kernel to KleidiAI int4 with a before/after benchmark on M-series Mac. Recorded as video + notebook + transcript in `demos/kernel-port/`.
4. **Distribution**: published to PyPI and registered on registry.modelcontextprotocol.io via the `mcp-publisher` CLI. Install docs in README.
5. **TypeScript port (fast-follow)**: shipped within weeks of v1.0, npm publish, shared schema validated in CI.

## Out of Scope for v1 (deliberately)

- ExecuTorch + KleidiAI integration coverage (v1.5).
- KleidiAI core C kernels coverage (v2).
- Neoverse, Cortex-M, Mali, Ethos coverage (different products).
- Hosted-server / SaaS layer. v1 is stdio + HTTP only; no infra.
- Bridget integration of any kind. See `arm-mcp-out-of-scope.md` in Bridget's memory for the full rationale.
- Novel retrieval implementation. Use off-the-shelf retrieval; the differentiator is corpus quality + evals, not retrieval cleverness.

## Load-Bearing Constraints

- **Corpus quality is the moat.** Anyone can stand up an MCP server. "Best in genre" means the corpus is hand-curated for KleidiAI + llama.cpp Arm optimization, with provenance (source URL, fetch date, SHA-256) committed in `corpus/manifest.yaml`. Cutting corners on curation defeats the entire pitch.
- **Evals are committed as artifacts.** `evals/reports/` is regenerated and committed on every change to corpus or server. Reviewers see scores without running anything. This is the bullet most candidates skip — don't.
- **Cross-SDK schema is one source of truth.** Python + TypeScript servers must expose identical tool schemas. CI enforces parity. Drift breaks the "across different SDKs" claim that the entire repo's pitch rests on.
- **No fabricated corpus.** Every doc in `corpus/` comes from a real source URL with a fetch date recorded in `corpus/manifest.yaml`. If a source disappears, the entry stays with a `removed_at:` note and the reason. Never paraphrase or summarize a doc into the corpus — the agent is reasoning over real source text, or it's reasoning over nothing.

## Working Conventions

### Workflow

- Plan before coding on non-trivial changes; one-line tweaks just ship.
- TDD when scope is genuinely testable (retrieval scoring, schema validation, kernel-port demo logic, manifest hashing).
- For UI work (eval report rendering, demo notebooks): iterate via the actual rendered output, not assumptions.
- Don't add features, refactor, or introduce abstractions beyond the current task. Three similar lines beats premature abstraction.
- Default to no comments. Only add when the *why* is non-obvious.

### Reader-facing documents (docs/)

- **The workbook (`docs/workbook.md`) is written in plain language, generous
  to the reader**: every term of art, acronym, or piece of jargon is fully
  explained in plain language at first use (the ubiquitous ones live in its
  baseline-vocabulary section). Answers are fully worked — no gotchas, no
  busywork; numbers real, derivations carried through, primary sources named.
  This standard applies to all reader-facing documents under `docs/`.
- Keep the workbook current: when facts change (new eval runs, the recorded
  demo, publishes), update the affected answers or add a dated section —
  don't let it drift from the repo it describes.

### Response style

- Concise beats thorough. Lead with recommendation, then tradeoff.
- Push back when the user proposes something that contradicts `v0-decisions.md` or the load-bearing constraints above.
- Ask before expanding scope.

### Project hygiene

- **No "Claude" brand in product artifacts.** No "Claude" in user-facing strings, package metadata, code, code comments, documentation, or commit messages. No `Co-Authored-By: Claude` trailers. Internal Claude Code paths (`CLAUDE.md`, `.claude/commands/`) are fine to reference by filename.
- **Every corpus entry has provenance.** Source URL + fetch date + SHA-256 in `corpus/manifest.yaml`. No undocumented files under `corpus/`.
- **Evals don't lie.** Never tune the QA set to make the server look better. Add hard questions deliberately. A regression in eval scores is a signal, not a thing to mask.

### Git / commits

- Commit messages explain the *why*. The diff shows the *what*.
- Don't commit until asked. Batch related changes into one commit unless told to split.
- Never amend pushed commits without explicit permission. Never force-push to main.

### Slash commands

- Slash commands are operational checklists for real workflows. Add a command when there's a workflow worth walking through. Don't write speculative commands against imagined behavior — `.claude/commands/` stays empty until there's something concrete to encode.
- Expected commands to add as machinery lands: `/eval-run` (after M2), `/corpus-add` (after M1), `/schema-check` (after M5), `/release` (after M4), `/demo-record` (after M3).
