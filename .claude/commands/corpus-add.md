# /corpus-add — add a provenance-verified doc to the corpus

Add a new source document under `corpus/` with full provenance in
`corpus/manifest.yaml`. Corpus quality is the moat: no fabricated or
paraphrased content, ever — the committed file must be byte-identical to the
fetched source.

Arguments: the source URL (a GitHub blob URL or similar), e.g.
`/corpus-add https://github.com/ARM-software/kleidiai/blob/main/docs/foo.md`

## Steps

1. **Resolve the source**: derive the `raw_url` (for GitHub:
   `raw.githubusercontent.com/<org>/<repo>/<ref>/<path>`) and pin the commit —
   resolve the branch to a commit SHA at fetch time (GitHub API
   `/repos/<org>/<repo>/commits/<branch>` or `git ls-remote`).

2. **Fetch exactly, hash exactly**:

   ```sh
   curl -fsSL "<raw_url_at_pinned_commit>" -o corpus/<subdir>/<name>.md
   shasum -a 256 corpus/<subdir>/<name>.md
   ```

   Do not reformat, trim, or annotate the file. The SHA-256 is of the bytes
   as fetched.

3. **Check the license** in the source repo (LICENSE file / SPDX header).
   Share-alike licenses (e.g. CC-BY-SA-4.0, like the learn-arm doc) carry
   obligations at publish time — note them.

4. **Append the manifest entry** to `corpus/manifest.yaml`, matching the
   existing shape — all fields required:

   ```yaml
   - id: <kebab-case-id>
     url: <human URL>
     raw_url: <raw URL>
     commit: <full 40-char SHA>
     fetched_at: <ISO-8601 UTC, actual fetch time>
     sha256: <hex digest>
     path: <path relative to corpus/>
     license: <SPDX id>
     description: <one line: what the doc canonically answers>
   ```

5. **Verify**: the provenance tests must pass —

   ```sh
   cd packages/server-py && .venv/bin/python -m pytest tests/test_provenance.py -q
   ```

6. **Measure the impact**: a corpus change moves retrieval scores. Run
   `/eval-run` (at minimum step 1, dev_check) and note the movement. Grow
   `evals/questions.yaml` with questions the new doc canonically answers —
   in a separate, dedicated commit from the corpus add.

7. **Commit** doc + manifest together, message stating what the doc covers
   and why it earns corpus space.

## If a source disappears later

Keep the manifest entry, add `removed_at:` with the reason. Never silently
delete corpus entries.
