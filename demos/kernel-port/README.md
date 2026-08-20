# Kernel-port demo (M3)

The headline demo: an agent uses `mcp-server-kleidiai` to port a real f32
matmul kernel to KleidiAI int4, with a before/after benchmark on an M-series
Mac (Apple M5 Pro: FEAT_DotProd, FEAT_I8MM, FEAT_SME). Recorded as video +
transcript + notebook per `v0-decisions.md`.

## Layout

- `src/matmul_f32.cpp` — the kernel being ported: a plain f32 matmul with
  weights in `[N, K]` row-major (llama-style engine layout). This is the
  "before" state the recorded session starts from.
- `src/matmul_int4_kleidiai.{h,cpp}` — the port (rehearsal copy): weights
  quantized to int4 per-channel and packed once at construction
  (`kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0`), LHS dynamically quantized+packed on
  every run (`kai_lhs_quant_pack_qai8dxp_f32`), then the i8mm matmul variant.
- `src/main.cpp` — benchmark harness. Times both implementations on
  LLM-shaped GEMMs (decode M=1, batch M=32, prompt M=256 at N=K=4096),
  reports median ms / GFLOP/s / weight bytes / speedup, and checks each
  against the f32 result (`rel_rmse`). Weight prep is untimed (static in
  inference); LHS quantization is timed (dynamic).
- `build.sh` — clang build: kai micro-kernels as C, harness as C++,
  `-O3 -march=armv8.2-a+dotprod+i8mm` (+`-ffast-math` for the C++ side).
  Fast-math is deliberate: the baseline must be a competently vectorized f32
  kernel, not a strawman.
- `fetch_kleidiai.sh` — clones ARM-software/kleidiai into `third_party/`
  (gitignored) pinned to `b87ef9c94f45f11c81a6b1fdaed1b2b45ea58c0c` — the
  same commit the corpus docs were fetched at (`corpus/manifest.yaml`), so
  the code the agent reads matches the docs it retrieves.

## Rehearsal numbers (2026-08-20, M5 Pro, single thread)

The port was rehearsed off-camera to de-risk the recording; the recorded
session re-derives it via the MCP server from the baseline-only state.

| shape | impl | median ms | GFLOP/s | weights MB | rel RMSE | speedup |
|---|---|---|---|---|---|---|
| decode (M=1) | f32 baseline | 0.951 | 35.3 | 67.1 | 0 | 1.00x |
| decode (M=1) | KleidiAI int4 (i8mm) | 0.403 | 83.3 | 8.4 | 6.7e-02 | 2.36x |
| batch (M=32) | f32 baseline | 30.307 | 35.4 | 67.1 | 0 | 1.00x |
| batch (M=32) | KleidiAI int4 (i8mm) | 2.402 | 447.0 | 8.4 | 6.7e-02 | 12.62x |
| prompt (M=256) | f32 baseline | 245.575 | 35.0 | 67.1 | 0 | 1.00x |
| prompt (M=256) | KleidiAI int4 (i8mm) | 18.192 | 472.2 | 8.4 | 6.7e-02 | 13.50x |

Batch and prompt reuse each loaded weight across M rows and show the i8mm
throughput win directly. Decode's smaller 2.4x is the kernel's shape: the
8x8x32 variant computes an 8-row output tile that M=1 cannot amortize. This
explanation was tested (`experiments/gemv-decode.cpp`): a 1-row GEMV variant
(`1x8x32_neon_dotprod`) runs decode 2.14x faster than the GEMM incumbent
(0.186 vs 0.398 ms, 5.27x over f32) and loses at M=32 (5.897 vs 2.290 ms) —
the predicted crossover. The same experiment measured the per-call LHS
quantization at 0.001 ms (negligible, refuting an earlier guess), and the
f32 baseline's flat GFLOP/s across shapes indicates a compute ceiling, not
a bandwidth cap. Practical rule, matching llama.cpp's own integration:
GEMM variant for prefill, GEMV variant for decode.

## The recorded session

The agent's task mirrors `e2e-port-kernel-int4` in `evals/questions.yaml`:
starting from the baseline above, use `search_kleidiai_docs` to

1. identify the three required micro-kernels (LHS dynamic-quant+pack, RHS
   pack, matmul) for f32 × int4 per-channel on an i8mm CPU,
2. decode the chosen variant name via the naming grammar
   (`qai8dxp` / `qsi4cxp` / `8x8x32` / `neon` / `i8mm`),
3. write the port following the qsi4cx guide (RHS packed once, LHS
   quant+packed per call — weights are static, activations aren't),
4. wire the build and show the before/after table.

The port is judged the same way the eval judges it: it either compiles,
passes the RMSE check (for uniform [-1,1] test weights, int4 quantization
theory predicts rel RMSE ≈ 6.7e-2 — (range/15)/√12 over a weight RMS of
range/(2√3) — and the port matches it to two digits; a wrong port shows O(1)
error), and beats the baseline — or it doesn't.

## Run

```sh
./fetch_kleidiai.sh   # once; pinned checkout into third_party/
./build.sh
./build/bench
```
