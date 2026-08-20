# /release — publish a version (M4 machinery)

Publish flow: PyPI + GitHub release + MCP registry. Never run any publish
step on a dirty tree or red CI. Publishing is outward-facing — confirm with
the human before each irreversible step (PyPI upload, registry submit,
flipping the repo public).

## Pre-flight

1. Tree clean; `origin/main` up to date; CI green (`gh run list -L1`).
2. Eval record current: `evals/reports/report.md` reflects the corpus and
   server as they are (run `/eval-run` if anything moved).
3. Full local sequence green:
   `ruff check src tests && mypy src && pytest` in `packages/server-py`.
4. Version bumped consistently (they must match):
   - `packages/server-py/pyproject.toml` `version`
   - `packages/server-py/src/mcp_server_kleidiai/__init__.py` `__version__`
   - `distribution/registry.json` `version` (and package version)
5. `LICENSE` + `NOTICE` present; README install section says
   `pip install mcp-server-kleidiai` (not run-from-source) once on PyPI.
6. Stage the corpus into the packages (installed servers have no repo to
   walk up to): `python distribution/prepare_corpus.py prepare`. Run
   `clean` after building — the staged copies are gitignored and must never
   be committed.
7. Wheel sanity: `python -m build --wheel` — contains `patterns.yaml`,
   `_corpus/manifest.yaml`, and `LICENSE`; `pip install` into a scratch
   venv; stdio round-trip from a cwd outside the repo lists all three tools.

## Publish (confirm each step with the human)

1. With the corpus staged: `python -m build` (sdist + wheel), then
   `twine upload dist/*`; finish with `prepare_corpus.py clean`.
   (npm's prepack/postpack hooks do the staging automatically at M5.)
2. Tag + GitHub release: `git tag vX.Y.Z && git push origin vX.Y.Z`, then
   `gh release create vX.Y.Z --notes ...` (notes: score table, tool surface,
   demo numbers).
3. MCP registry: `mcp-publisher publish` with `distribution/registry.json`
   (login first; see registry.modelcontextprotocol.io docs).
4. First public release only: flip the repo public (`gh repo edit
   --visibility public`) — the human decides when.

## Post

1. Verify: `pip install mcp-server-kleidiai` from a clean venv works and the
   registry entry renders.
2. Update `where-to-begin.md` (milestone state) and the README status line.
3. `distribution/publish.py` automates the above as it solidifies — keep the
   script and this checklist in sync.
