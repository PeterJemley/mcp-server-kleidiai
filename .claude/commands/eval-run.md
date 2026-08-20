# /eval-run — run the retrieval eval and update the committed record

Run the eval suite and keep `evals/reports/` honest. The fast dev loop is for
iteration; the promptfoo run is the committed record. Never skip the report
update after a promptfoo run.

## Steps

1. **Fast check first** (seconds, catches obvious breakage):

   ```sh
   cd evals && ../packages/server-py/.venv/bin/python dev_check.py -v
   ```

   Compare against the current committed scores in `evals/reports/report.md`
   (overall and frozen-30). If this was just an experiment, stop here —
   dev_check runs don't get committed.

2. **The committed record** (promptfoo; node lives off the default PATH):

   ```sh
   cd evals
   export PATH="/opt/homebrew/bin:$PATH"
   PROMPTFOO_PYTHON=../packages/server-py/.venv/bin/python \
     ./node_modules/.bin/promptfoo eval --no-cache -o reports/report.json
   ```

3. **Update `evals/reports/report.md`**: refresh the score table, the
   remaining-failures table (id / want / got / kind / category), and append
   to the prior-runs table. A regression is a signal — record it, don't
   mask it. New failure categories get named and grouped like the existing
   A/B/C/D ones.

4. **Sync the strict-xfail smoke tests**
   (`packages/server-py/tests/test_retrieval.py`): a fixed failure demands
   un-marking its xfail; a new known residual gets a marked test. Then run:

   ```sh
   cd packages/server-py && .venv/bin/python -m pytest tests -q
   ```

5. **Commit** report.json + report.md (+ any xfail changes) in a dedicated
   eval commit whose message states the score movement and why.

## Rules (from CLAUDE.md — do not bend)

- Never tune questions to flatter the server; ground-truth changes only
  under the † widening policy, in dedicated commits.
- Retriever changes are decided by measured A/B, recorded in report.md.
