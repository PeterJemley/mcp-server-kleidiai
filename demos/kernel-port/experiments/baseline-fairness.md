# Preregistration: is the f32 baseline a fair "before"?

- **Written:** 2026-10-03, before any run.
- **Commit:** the commit that adds this file. Its git timestamp is the
  evidence that the plan came first, and `run-baseline-fairness.sh` refuses
  to run until this file is committed.
- **Status:** Q1 and Q2 are confirmatory; the Accelerate comparison is
  exploratory.

## Why this experiment exists

The demo reports the KleidiAI int4 port as 2.36× faster than f32 at decode
(M=1) and 12.62–13.50× faster at batch (M=32) and prompt (M=256) sizes
(`../README.md`).

The f32 "before" is `src/matmul_f32.cpp`. For every input row it walks the
entire 4096×4096 weight matrix (67 MB) again, so its weight traffic per
FLOP is the same at every M. The int4 kernel computes multi-row tiles and
reuses each weight it loads across several rows.

Two consequences follow, and each becomes a question:

- **The "compute ceiling" reading may be wrong.** The demo README and
  workbook Q30 read the baseline's flat ~35 GFLOP/s across shapes as a
  compute ceiling. A memory-bandwidth limit predicts the same flat line for
  this loop: at every shape it moves about 70 GB/s of weights (70.6, 70.9
  and 70.0 GB/s computed from the published table). The published numbers
  can't tell the two apart.
- **The headline may bundle weight reuse with int4.** At M=32 and M=256 the
  speedup combines three things: int4 data, i8mm instructions, and weight
  reuse that the f32 loop lacks. Only the first two are what porting to
  KleidiAI int4 is meant to show.

## Q1 — compute-limited or memory-limited?

**Claim under test** (demo README; workbook Q30): the published f32 loop
runs at a compute ceiling, not a bandwidth cap, at N=K=4096.

**Design.** Run the published loop at M=32 and K=4096, varying only N: 128,
256, 1024 and 4096. That puts 2, 4, 16 and 64 MB of weights in play. The
inner loop is identical at every N; only the working set grows.

**Primary measure.**

R = (higher GFLOP/s of N=128 and N=256) ÷ (GFLOP/s at N=4096)

computed per run; the verdict uses the median of the five runs.

| Hypothesis | Predicts |
|---|---|
| Compute ceiling (the published reading) | R between 0.85 and 1.15 |
| Memory-bandwidth limit | R ≥ 1.5 |
| Mixed, or limited by an intermediate cache level | R between those bands |

**Decision rule** (covers every outcome):

| Outcome | Condition |
|---|---|
| Compute-limited; the reading stands | 0.85 ≤ R ≤ 1.15 |
| Memory-limited; the reading is refuted | R ≥ 1.5 |
| Inconclusive | anything else |

## Q2 — how much of the headline survives a reuse-matched baseline?

**Claim under test** (README headline): the int4 port is 12.62× (M=32) and
13.50× (M=256) faster than f32.

**Design.** Add two f32 loops identical to the published one, except that
4 or 8 input rows share each pass over a weight row. Each weight loaded
then serves 4 or 8 rows. These loops are a *floor* on what reuse buys f32,
not a ceiling: a fully tiled f32 kernel would do better.

**Primary measures, per run, at M=256** (M=32 is secondary, same rule):
- S_published = published loop time ÷ int4 time
- S_reuse = (faster of the 4-row and 8-row loops) ÷ int4 time
- share = S_reuse ÷ S_published (median across runs)

**Decision rule** (covers every outcome):

| Outcome | Condition | What changes |
|---|---|---|
| The headline stands as stated | share ≥ 0.8 | add S_reuse next to it |
| The headline is restated | share < 0.8 | lead with S_reuse; give the published-loop figure second, labelled as such |

The 0.8 threshold is a disclosure rule: if weight reuse accounts for more
than a fifth of the headline, the headline must say so.

## Secondary (exploratory, no prediction): Accelerate

Apple's Accelerate `cblas_sgemm` is run single-threaded
(`VECLIB_MAXIMUM_THREADS=1`) at the published shapes. It is what most Mac
code would call, so it is the strongest reasonable f32 baseline. Accelerate
can use the chip's matrix hardware, so it may beat the int4 port at some
shapes. No prediction is made. Whatever it shows is reported next to the
headline, including a loss.

## Controls

- **Correctness, with a gate that can fail.**
  - Every row is checked against the published loop's output: the f32
    variants at relative RMSE ≤ 1e-4 (they differ only in summation order),
    int4 at ≤ 8e-2 (theory gives 1/15 ≈ 6.7e-2 for these uniform weights).
  - At startup the program confirms that a 1% perturbation fails the f32
    gate.
  - Each output buffer is filled with NaN before its implementation runs,
    so an implementation that writes nothing fails instead of inheriting
    the previous row's result.
  - Any failure voids the run, and the program exits non-zero.
- **Link to the published run.** The published loop must land within ±10%
  of the published GFLOP/s (35.3, 35.4 and 35.0 at M=1, 32 and 256). The
  int4 speedup over it must land within ±10% of 2.36, 12.62 and 13.50. If
  either fails, the machine or toolchain has drifted: the outcomes are
  still reported, marked as not comparable to the README.
- **M=1 fallback.** At M=1 the 4-row and 8-row loops fall back to the
  published loop, so they must time within ±10% of it. If they don't,
  something other than reuse is moving the timings.
- **Same inputs.** Every row uses the published benchmark's inputs (uniform
  [−1, 1], seed 42), regenerated per shape exactly as `src/main.cpp` does.

## Runs and analysis

- **Five separate process runs**, 10 s apart, on AC power, with Terminal in
  the foreground.
- **Within a run:** each row takes one untimed warmup, then at least 10
  timed repetitions and at least 1.5 s of timing, capped at 200. The row
  reports the median, minimum and maximum.
- **Across runs:** `summarize_baseline_fairness.py` computes the median and
  range of the per-run medians, the controls, R and share, and applies the
  rules above. Every number in the summary comes from the run files.
- **Noise versus the thresholds:** the published record shows 1–3%
  run-to-run spread for the same kernel, far smaller than the gaps between
  the decision thresholds (1.15 vs 1.5; 0.8).

## Stopping rule

Run once: `./experiments/run-baseline-fairness.sh`, which makes five
processes. A correctness failure is a bug. Fix it, log the fix below, and
re-run all five. Never re-run to get different numbers.

## Limitations, stated in advance

- **One machine** (Apple M5 Pro), one thread, one weight distribution
  (uniform). Real model weights differ.
- **The 4- and 8-row loops are simple** and understate what a tuned f32
  kernel can do. The Accelerate row is the measured upper reference.
- **Cache residency isn't proven.** If neither 2 MB nor 4 MB of weights
  stays in cache on this chip, Q1's test loses sensitivity. A result near
  R = 1 would then need that caveat.

## Deviation log

- 2026-10-03: the run `results/2026-10-03-1621-baseline-fairness` was made
  on battery power, not AC as planned; its manifest records this. Results
  were seen before this entry. Effect: the run stands as recorded. Every
  control passed, the published rows reproduced within ±10%, and every
  verdict compares rows from the same run. A replication on AC power is
  declared here, before it runs: it is the run that follows the protocol,
  both runs are reported, and if their verdicts differ, the AC run's
  verdicts govern.
- 2026-10-04: this program's timing loop, `rel_rmse`, `poison()` and
  `all_finite()` moved into the shared `src/bench_harness.h`
  (`bench-harness.md`). The protocol is unchanged: the same warmup, the same
  repetition rule (at least 10 repetitions and 1.5 s, at most 200), and the
  same median, minimum and maximum. `bench-harness.md` P1 and P2 check
  this: the same number of calls, and identical output once timings are
  masked. The one difference is that `rel_rmse` now returns plain RMSE when
  the reference is all zero instead of dividing by zero; no reference here
  is all zero. The pending AC-power replication runs the shared-header
  build.

## Outcome

- Run `2026-10-03-1621` (battery power; see the deviation log):
  - **Q1: compute-limited.** R = 1.07, and 1.06–1.07 in every run.
  - **Q2: the headline is restated.** The share surviving is 0.51 at M=256
    and 0.52 at M=32.
  - Computed summary:
    `../results/2026-10-03-1621-baseline-fairness/summary.md`.
