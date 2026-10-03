# /demo-record — run the M3 recording session

Walk the kernel-port demo recording end to end. Full context in
`demos/kernel-port/recording-plan.md`. The human drives the recorded agent
session; this checklist wraps it.

## Pre-flight (assistant)

1. Tree clean, CI green on origin/main (`git status`, `gh run list -L1`).
2. Server responds over stdio with all three tools (`.mcp.json` registers it;
   spot-check with an stdio client round-trip).
3. `demos/kernel-port/fetch_kleidiai.sh` checkout present at the pinned commit.
4. Build the recording workspace outside the repo:
   `demos/kernel-port/demo-reset.sh workspace ~/msk-recording`. It refuses on a
   dirty tree. It creates a new git repository whose only commit is the
   baseline (f32 kernel, baseline-only harness and build script; no port,
   README recipe, recording plan or experiments, and no history), copies the
   KleidiAI checkout, registers the server in its `.mcp.json`, and refuses if
   any of the port's identifiers survive. (Recording inside this repo isn't
   an option: git status, diff and log there would show the port.)
5. Baseline builds and runs in the workspace:
   `cd ~/msk-recording && ./build.sh && ./build/bench` — f32-only table.
6. Machine on AC power, heavy apps closed, screen recorder ready.

## Recording (human)

1. Start screen capture (QuickTime is fine).
2. In a fresh agent session started in `~/msk-recording` (its `.mcp.json`
   connects the `kleidiai` server), paste the task prompt from
   `demos/kernel-port/recording-plan.md` in this repo.
3. Let the agent work; intervene only if it stalls. The agent should be
   calling `search_kleidiai_docs` / `get_kleidiai_pattern` /
   `plan_kernel_port` and citing doc URLs. Reads outside the workspace show
   in the transcript; note any.
4. Run the final before/after benchmark on camera.
5. Stop capture. Export the session transcript.

## Post (assistant)

1. Compare the agent's port (`git -C ~/msk-recording diff HEAD`) with the
   rehearsal copy in `demos/kernel-port/src/`; differences are interesting,
   not failures.
2. Produce the committed artifacts in `demos/kernel-port/`: cleaned
   `transcript.md` (complete and honest), the agent's port and its workspace
   diff, the notebook narrating baseline → tool calls → port → benchmark with
   the real numbers, README link to the video. Commit.
3. Success bar (same as the eval): the recorded port compiles, RMSE matches
   int4 quantization theory (~6.7e-2 on uniform test weights), and beats the
   f32 baseline.
