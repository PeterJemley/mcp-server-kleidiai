# Planned slash commands

Per the convention in `CLAUDE.md`, `.claude/commands/` stays empty until each workflow has real underlying machinery. These are the commands queued to add as milestones land. Each becomes a file in `.claude/commands/<name>.md` when its machinery is in place.

| Command | Added after | What it does |
|---|---|---|
| `/corpus-add <url>` | M1 — **added 2026-08-20** | Fetch URL, hash it, append entry to `corpus/manifest.yaml`, commit doc + manifest atomically. |
| `/eval-run` | M2 — **added 2026-08-20** | Execute the eval suite, regenerate `evals/reports/`, diff against last report, commit. |
| `/demo-record <name>` | M3 (kernel-port pipeline) | Walk a demo end-to-end, capture transcript + benchmark to `demos/<name>/`. |
| `/release [major\|minor\|patch]` | M4 (`publish.py` wired) | Version bump, git tag, PyPI publish, MCP registry sync via `mcp-publisher`. |
| `/schema-check` | M5 (TypeScript port) | Diff Python vs TypeScript tool schemas; fail on drift. |

Possible additions as the corpus grows:

- `/corpus-refresh` — re-fetch every entry in `corpus/manifest.yaml`, compare hashes, surface stale entries with diffs.
- `/manifest-verify` — confirm every entry exists on disk with matching SHA-256 (CI candidate).

Rule from `CLAUDE.md`: don't write a command speculatively. Add when the workflow exists.
