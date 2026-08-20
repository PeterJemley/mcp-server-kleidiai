# M3 recording plan — the agent session

Written 2026-08-20 for the next session. The port is rehearsed and works
(numbers in `README.md`); what remains for M3 is capturing the *recorded
agent session* — the artifact `v0-decisions.md` locked as video + transcript
+ notebook in this directory.

## What gets recorded, and why it's the deliverable

A screen recording of a live agent session in a terminal-based MCP client
with `mcp-server-kleidiai` connected. The agent starts
from the baseline-only code and, using `search_kleidiai_docs`, must:

1. discover that f32 × int4 per-channel on an i8mm CPU needs three
   micro-kernels — LHS dynamic-quant+pack, RHS pack, matmul;
2. decode the variant name
   (`qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm`) via the naming-grammar doc;
3. write the port following the qsi4cx guide (RHS packed once, LHS
   quant+packed per run);
4. wire the build and produce the before/after table.

This mirrors `e2e-port-kernel-int4` in `evals/questions.yaml`. It's the
proof that the server is useful *to an agent* — the whole portfolio pitch.
The port either compiles, matches int4 quantization theory on RMSE
(~6.7e-2 on uniform test weights), and beats the baseline — or it doesn't.

## Division of labor

**Only the human can:** start/stop the screen recording, drive the live
agent session, and vouch that the committed transcript is the real one.
This demo is portfolio evidence; it must be a genuine session, not
synthesized.

**The assistant preps everything else** (next session, before recording):

- [ ] Commit the current working tree first (rehearsal port stays in git
      history as the safety net).
- [ ] Write `demo-reset.sh`: flips this directory to the *before* state
      (moves `src/matmul_int4_kleidiai.{h,cpp}` aside, restores the
      baseline-only `main.cpp` and `build.sh`) and back. Honest-recording
      requirement: the agent must re-derive the port, not find it in `src/`.
      `README.md` already discloses the off-camera rehearsal — no sleight
      of hand, but no answer key on disk either.
- [ ] Register the server with the MCP client: stdio config from the root
      README (`packages/server-py/.venv/bin/python -m mcp_server_kleidiai`).
- [ ] Pre-flight checklist: server responds over stdio, tool listed,
      baseline builds and runs, `fetch_kleidiai.sh` checkout present,
      screen-recording tool ready (QuickTime is fine).
- [ ] Draft the exact task prompt to paste to the agent (below), tuned so
      the agent must consult the server rather than its own training data —
      e.g. require cited doc ids/URLs for each kernel choice.
- [ ] Write `/demo-record` in `.claude/commands/` (due after M3 per
      `slash-commands.md`) encoding this checklist.

**During recording (human):** start capture → paste prompt → let the agent
work (intervene only if it stalls) → run the final benchmark on camera →
stop capture. Save the session transcript.

**After recording (assistant):** turn the raw transcript into the committed
artifacts — `transcript.md` (cleaned, complete, honest), a notebook that
narrates baseline → search → port → benchmark with the real numbers, and a
README link to the video. Compare the agent's port to the rehearsal copy;
differences are interesting, not failures.

## Draft task prompt (starting point, refine next session)

> In `demos/kernel-port/` there's an f32 matmul (`src/matmul_f32.cpp`) with
> a benchmark harness. Port it to KleidiAI int4 per-channel for this
> machine's CPU (Apple M5 Pro, i8mm). Use the `search_kleidiai_docs` tool
> to determine which micro-kernels you need and how to call them — cite the
> doc id and URL for every kernel you pick and explain the variant name you
> chose using the naming grammar. Weights may be packed once; LHS
> quantization must happen per run. Extend `build.sh` (KleidiAI checkout is
> in `third_party/kleidiai`), verify correctness against the f32 result,
> and show the before/after benchmark table.

## Known constraints

- No model API key in this repo's env vars — but interactive agent clients
  carry their own model auth, so that gate (which blocks the *promptfoo
  agentic eval*) does not block this recording.
- Target hardware is this machine; keep it on AC power and quit heavy apps
  before benchmarking on camera.
- Session length: rehearsal suggests the port is ~30 minutes of agent work;
  budget an hour of recording and trim in edit.
