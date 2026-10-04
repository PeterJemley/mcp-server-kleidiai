# Baseline-fairness summary (5 runs)

## Every row: median across runs (range of the per-run medians)

| part | M | N | impl | median ms | range ms | GFLOP/s |
|---|---|---|---|---|---|---|
| shapes | 1 | 4096 | Accelerate sgemm | 0.535 | 0.500–0.542 | 62.7 |
| shapes | 1 | 4096 | KleidiAI int4 | 0.392 | 0.391–0.394 | 85.6 |
| shapes | 1 | 4096 | f32 4-row loop | 0.913 | 0.884–0.935 | 36.8 |
| shapes | 1 | 4096 | f32 8-row loop | 0.919 | 0.878–0.936 | 36.5 |
| shapes | 1 | 4096 | f32 published loop | 0.915 | 0.880–0.941 | 36.7 |
| shapes | 32 | 4096 | Accelerate sgemm | 1.558 | 1.549–1.638 | 689.2 |
| shapes | 32 | 4096 | KleidiAI int4 | 2.266 | 2.190–2.427 | 473.8 |
| shapes | 32 | 4096 | f32 4-row loop | 14.606 | 14.156–14.767 | 73.5 |
| shapes | 32 | 4096 | f32 8-row loop | 17.198 | 16.945–17.544 | 62.4 |
| shapes | 32 | 4096 | f32 published loop | 28.594 | 28.139–29.129 | 37.6 |
| shapes | 256 | 4096 | Accelerate sgemm | 5.739 | 5.663–5.946 | 1496.8 |
| shapes | 256 | 4096 | KleidiAI int4 | 18.228 | 17.933–18.366 | 471.2 |
| shapes | 256 | 4096 | f32 4-row loop | 118.434 | 115.979–125.262 | 72.5 |
| shapes | 256 | 4096 | f32 8-row loop | 140.700 | 137.331–149.674 | 61.1 |
| shapes | 256 | 4096 | f32 published loop | 228.332 | 224.619–238.057 | 37.6 |
| sweep | 32 | 128 | f32 8-row loop | 0.545 | 0.539–0.557 | 61.6 |
| sweep | 32 | 128 | f32 published loop | 0.850 | 0.808–0.860 | 39.5 |
| sweep | 32 | 256 | f32 8-row loop | 1.099 | 1.083–1.125 | 61.1 |
| sweep | 32 | 256 | f32 published loop | 1.732 | 1.668–1.799 | 38.7 |
| sweep | 32 | 1024 | f32 8-row loop | 4.397 | 4.346–4.458 | 61.0 |
| sweep | 32 | 1024 | f32 published loop | 7.041 | 6.947–7.199 | 38.1 |
| sweep | 32 | 4096 | f32 8-row loop | 17.527 | 17.283–17.781 | 61.3 |
| sweep | 32 | 4096 | f32 published loop | 29.516 | 28.422–30.189 | 36.4 |

## Controls

- Link to the published table, M=1: f32 36.7 GFLOP/s vs 35.3 (within ±10%); int4 speedup 2.32x vs 2.36x (within ±10%)
- Link to the published table, M=32: f32 37.6 GFLOP/s vs 35.4 (within ±10%); int4 speedup 12.52x vs 12.62x (within ±10%)
- Link to the published table, M=256: f32 37.6 GFLOP/s vs 35.0 (within ±10%); int4 speedup 12.71x vs 13.5x (within ±10%)
- M=1 fallback control: f32 4-row loop takes 1.00x the published loop's time (within ±10%; it runs the same code at M=1)
- M=1 fallback control: f32 8-row loop takes 1.00x the published loop's time (within ±10%; it runs the same code at M=1)

## Q1 — is the published f32 loop compute-limited or memory-limited at N=K=4096?

R = GFLOP/s with weights in cache (best of N=128, 256) ÷ GFLOP/s at N=4096 = **1.10** (per run: 1.13, 1.13, 1.04, 1.07, 1.10)

Verdict: **COMPUTE-LIMITED — the 'compute ceiling' reading stands**

## Q2 — how much of the int4 speedup survives a reuse-matched f32 loop?

- M=256 (primary): vs published loop **12.71x**, vs best of 4-/8-row loop **6.48x**; share surviving **0.52** → restate the headline against the reuse-matched f32 loop; give the published-loop figure second
- M=32 (secondary): vs published loop **12.52x**, vs best of 4-/8-row loop **6.45x**; share surviving **0.51** → restate the headline against the reuse-matched f32 loop; give the published-loop figure second

## Secondary (exploratory, no prediction): int4 vs Accelerate sgemm, single-threaded

- M=1: int4 is 1.36x Accelerate's speed (per run: 1.38, 1.37, 1.28, 1.29, 1.36)
- M=32: int4 is 0.69x Accelerate's speed (per run: 0.71, 0.68, 0.69, 0.70, 0.67) — Accelerate f32 is faster than the int4 port here
- M=256: int4 is 0.32x Accelerate's speed (per run: 0.33, 0.32, 0.32, 0.31, 0.31) — Accelerate f32 is faster than the int4 port here
