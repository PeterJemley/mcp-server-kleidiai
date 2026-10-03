# Baseline-fairness summary (5 runs)

## Every row: median across runs (range of the per-run medians)

| part | M | N | impl | median ms | range ms | GFLOP/s |
|---|---|---|---|---|---|---|
| shapes | 1 | 4096 | Accelerate sgemm | 0.472 | 0.469–0.505 | 71.1 |
| shapes | 1 | 4096 | KleidiAI int4 | 0.391 | 0.371–0.391 | 85.8 |
| shapes | 1 | 4096 | f32 4-row loop | 0.875 | 0.841–0.892 | 38.3 |
| shapes | 1 | 4096 | f32 8-row loop | 0.877 | 0.839–0.895 | 38.3 |
| shapes | 1 | 4096 | f32 published loop | 0.882 | 0.843–0.890 | 38.0 |
| shapes | 32 | 4096 | Accelerate sgemm | 1.550 | 1.522–1.620 | 692.7 |
| shapes | 32 | 4096 | KleidiAI int4 | 2.270 | 2.244–2.329 | 473.0 |
| shapes | 32 | 4096 | f32 4-row loop | 14.552 | 14.468–14.776 | 73.8 |
| shapes | 32 | 4096 | f32 8-row loop | 17.222 | 17.102–17.805 | 62.3 |
| shapes | 32 | 4096 | f32 published loop | 27.814 | 26.965–28.349 | 38.6 |
| shapes | 256 | 4096 | Accelerate sgemm | 5.701 | 5.639–5.912 | 1506.7 |
| shapes | 256 | 4096 | KleidiAI int4 | 17.902 | 17.684–17.996 | 479.8 |
| shapes | 256 | 4096 | f32 4-row loop | 116.704 | 115.326–119.151 | 73.6 |
| shapes | 256 | 4096 | f32 8-row loop | 140.136 | 136.973–141.206 | 61.3 |
| shapes | 256 | 4096 | f32 published loop | 227.516 | 223.321–238.269 | 37.8 |
| sweep | 32 | 128 | f32 8-row loop | 0.535 | 0.534–0.538 | 62.7 |
| sweep | 32 | 128 | f32 published loop | 0.824 | 0.799–0.830 | 40.7 |
| sweep | 32 | 256 | f32 8-row loop | 1.077 | 1.073–1.085 | 62.3 |
| sweep | 32 | 256 | f32 published loop | 1.700 | 1.663–1.722 | 39.5 |
| sweep | 32 | 1024 | f32 8-row loop | 4.300 | 4.257–4.333 | 62.4 |
| sweep | 32 | 1024 | f32 published loop | 6.924 | 6.805–7.020 | 38.8 |
| sweep | 32 | 4096 | f32 8-row loop | 17.184 | 17.037–17.869 | 62.5 |
| sweep | 32 | 4096 | f32 published loop | 27.870 | 27.346–28.497 | 38.5 |

## Controls

- Link to the published table, M=1: f32 38.0 GFLOP/s vs 35.3 (within ±10%); int4 speedup 2.26x vs 2.36x (within ±10%)
- Link to the published table, M=32: f32 38.6 GFLOP/s vs 35.4 (within ±10%); int4 speedup 12.39x vs 12.62x (within ±10%)
- Link to the published table, M=256: f32 37.8 GFLOP/s vs 35.0 (within ±10%); int4 speedup 12.65x vs 13.5x (within ±10%)
- M=1 fallback control: f32 4-row loop takes 1.00x the published loop's time (within ±10%; it runs the same code at M=1)
- M=1 fallback control: f32 8-row loop takes 1.00x the published loop's time (within ±10%; it runs the same code at M=1)

## Q1 — is the published f32 loop compute-limited or memory-limited at N=K=4096?

R = GFLOP/s with weights in cache (best of N=128, 256) ÷ GFLOP/s at N=4096 = **1.07** (per run: 1.07, 1.07, 1.06, 1.07, 1.07)

Verdict: **COMPUTE-LIMITED — the 'compute ceiling' reading stands**

## Q2 — how much of the int4 speedup survives a reuse-matched f32 loop?

- M=256 (primary): vs published loop **12.65x**, vs best of 4-/8-row loop **6.52x**; share surviving **0.51** → restate the headline against the reuse-matched f32 loop; give the published-loop figure second
- M=32 (secondary): vs published loop **12.39x**, vs best of 4-/8-row loop **6.47x**; share surviving **0.52** → restate the headline against the reuse-matched f32 loop; give the published-loop figure second

## Secondary (exploratory, no prediction): int4 vs Accelerate sgemm, single-threaded

- M=1: int4 is 1.27x Accelerate's speed (per run: 1.27, 1.22, 1.29, 1.21, 1.27)
- M=32: int4 is 0.68x Accelerate's speed (per run: 0.68, 0.70, 0.68, 0.71, 0.68) — Accelerate f32 is faster than the int4 port here
- M=256: int4 is 0.32x Accelerate's speed (per run: 0.32, 0.32, 0.33, 0.32, 0.31) — Accelerate f32 is faster than the int4 port here
