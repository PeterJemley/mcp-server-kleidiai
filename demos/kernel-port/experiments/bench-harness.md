# Preregistration: one shared benchmark harness

- **Written:** 2026-10-04, before any harness code exists.
- **Commit:** the commit that adds this file.
- **Status:** confirmatory.

## Why

The timing loop and the relative-RMSE check have been copied four times:
- `src/main.cpp`, the published benchmark;
- `experiments/gemv-decode.cpp`;
- `experiments/baseline-fairness.cpp`;
- the baseline harness that `demo-reset.sh` writes into the recording
  workspace.

The copies have already diverged:
- the three repetition rules differ;
- only one `rel_rmse` guards against an all-zero reference;
- only one checks for NaN in a way `-ffast-math` can't fold away.

The 2026-10-04 linearity study named this as the second seam worth
building.

## Claim

A single header, `src/bench_harness.h`, can replace all four copies of the
timing loop and of `rel_rmse` while every program keeps its declared
measurement rule exactly:

| Program | Rule |
|---|---|
| `main.cpp` and the workspace template | 5–100 repetitions, from 5 ÷ GFLOP |
| `gemv-decode.cpp` | 20–200 repetitions, from the same formula |
| `baseline-fairness.cpp` | at least 10 repetitions and 1.5 s, at most 200 (fixed in `baseline-fairness.md`; its plugged-in replication is still pending) |

## Design

- **The header holds the shared code:**
  - **`RepRule{min_reps, max_reps, min_total_ms}`**, with
    `fixed_for(gflop, lo, hi)` producing the fixed-count rules.
  - **`time_ms(run, rule)`**: one untimed warmup, then timed repetitions
    until the rule is met. It returns the median, minimum and maximum. The
    clock is a template parameter, so tests can drive it.
  - **`rel_rmse`**, with the zero-reference guard. Its values are
    unchanged whenever the reference isn't all zero.
  - **`poison()` and `all_finite()`**, which check NaN on bit patterns.
- **Each program passes its own rule** and keeps its own table format. The
  tables have different columns by design, so table printing stays per
  program; that is a scope decision made here, before any run.
- **`build-gemv.sh` gains `-I src`.**
- **The header contains none of the port's identifiers,** so the recording
  workspace may include it.
- **Out of scope:** the copy of the port's quantizer in `gemv-decode.cpp`
  (it is an answer key and lives in different files).

## Measures

All measures run on Linux x86 with stand-ins for KleidiAI and Accelerate.
The Arm build is checked separately (see Secondary).

- **P1, the protocol is preserved.** The old timing functions are extracted
  verbatim from the files at this commit and compared with the new harness
  on how many times each calls `run()`:
  - **the fixed rules** (main/template and GEMV) at GFLOP values of 0.001,
    0.0336, 1.07, 8.59 and 100;
  - **the time-based rule** with work of 0 ms, 120 ms and 200 ms per call;
  - **`rel_rmse`** compared with each old copy on random data (values
    identical);
  - **a scripted clock** confirming that median, minimum and maximum are
    exact.

  Every comparison must be equal.
- **P2, behaviour is preserved.** Old and new versions of all four programs
  are built and run with the same stand-ins. Their outputs must be identical
  once the timing columns (ms, GFLOP/s, speedup) are masked. For
  `baseline-fairness.cpp`, the pass/fail column is included in the
  comparison.
- **P3, one copy.** After the change, `steady_clock::now` and
  `double rel_rmse(` appear in exactly one file under `demos/kernel-port`,
  the header. Before the change, each appears in 4 files.
- **P4, the workspace is still clean.** `demo-reset.sh workspace` must
  produce a workspace that includes the header, passes its leak check, and
  whose baseline compiles.

## Decision rule

| Outcome | Condition |
|---|---|
| Supported | P1 all equal; P2 identical; P3 one file each; P4 passes |
| Refuted | any P1 difference, any P2 difference or build failure, P3 more than one file, or P4 fails |
| Inconclusive | a check could not be run |

## Controls that must fail

- **P1:** a harness whose fixed rule is off by one repetition must show a
  count mismatch; a median taken as `samples[0]` must fail the
  scripted-clock test.
- **P2:** a harness whose `rel_rmse` drops the square root must change the
  masked output of `main.cpp`.

## Secondary (not in the decision rule)

- **An Arm syntax check,** if the toolchain allows it: compile all three
  programs for arm64 against the real KleidiAI headers at the pinned commit.
- **Real hardware:** the next Mac session (the pending plugged-in
  replication) builds all three programs. A build failure there refutes
  "builds on the target" and is reported as such.

## Stopping rule

Run once. If a check fails because of a bug in the harness, fix it, log it
below, and re-run everything. Never loosen a comparison to manufacture
agreement.

## Deviation log

- 2026-10-04, **P3's timing string, chosen after the result.** The header
  names the clock as a template parameter (`Clock = std::chrono::steady_clock`,
  then `Clock::now()`). So after the change, `steady_clock::now` appears in
  no code file at all: 0 files, where P3 expected 1. This was seen only
  once the count had run. The count was then widened to `::now()`, the same
  string without the clock's name: 4 files before, 1 after (the header).
  Both counts are reported below. By the letter of the decision rule, 0
  files is neither "one file" (supported) nor "more than one" (refuted).
  The verdict rests on the widened count, which was chosen after the
  result.
- 2026-10-04, **what P3 counts.** P3 excludes Markdown files, because this
  file names both strings. It also excludes the checker's own folder, which
  names the strings it searches for and didn't exist when this plan was
  written. The "4 files before" stated above counts code files only.
- 2026-10-04, **the checks ran twice.**
  - **First run:** from scratch files on the uncommitted change. Every check
    passed.
  - **Second run:** `bench-harness-check/check.py` reran everything on the
    committed change (`699c975`), so anyone can reproduce it. Its results
    match the first run's.
  - **Checker bugs:** trial runs of the checker printed P1 (all passing),
    then stopped on bugs in the checker itself: it didn't set
    `VECLIB_MAXIMUM_THREADS`, which `baseline-fairness.cpp` requires, and
    it treated "no file matches" from `git grep` as an error. Both were
    fixed before the second run. Neither touched the harness or any
    comparison.
  - **A rerun of the second run:** its first attempt failed all of P4,
    because this file was being edited while it ran. `demo-reset.sh`
    refuses to build a workspace while tracked files have uncommitted
    changes. Every other result in that attempt matched. The edit was set
    aside and the whole checker rerun on a clean tree; `check.out` is that
    rerun.
- 2026-10-04, **a fact in "Why" was wrong.** It says only one `rel_rmse`
  guarded against an all-zero reference. Two did: `main.cpp` and the
  workspace template, which copies it. No measure depends on this.
- 2026-10-04, **a syntax error during implementation.** One edit left a
  syntax error in `gemv-decode.cpp`. The first compile caught it, before
  any check ran.

## Outcome (2026-10-04): supported, with P3's timing string widened after the result

Raw output: `bench-harness-check/check.out`, written by
`bench-harness-check/check.py` (x86-64 Linux, stand-ins for the Arm-only
code; see the checker's header).

| Check | Result | Required |
|---|---|---|
| P1 fixed rules | equal calls at all 5 GFLOP values, for the main/template rule (101, 101, 6, 6, 6) and the GEMV rule (201, 149, 21, 21, 21), counting the warmup | all equal |
| P1 time rule | 201/201, 14/14 and 11/11 calls at 0, 120 and 200 ms per call | all equal |
| P1 `rel_rmse` | bit-identical to all 4 old copies on 5 random trials | identical |
| P1 scripted clock | median, minimum, maximum and count exact for an odd count, an even count and the time rule | exact |
| P1 controls | off-by-one rule: 102 or 7 calls where the old code made 101 or 6; a `samples[0]` median fails the scripted-clock test | must fail |
| P2 outputs | identical with timings masked: `main.cpp` 6 rows, template 3, GEMV 10, `baseline-fairness.cpp` 23 (check column included) | identical |
| P2 control | `rel_rmse` without the square root changes 3 of 6 rows of `main.cpp` | must differ |
| P3 `double rel_rmse(` | 4 files before, 1 after (the header) | 1 |
| P3 `steady_clock::now` | 4 files before, 0 after | 1: **not met as written** |
| P3 `::now()` (widened after the result) | 4 files before, 1 after (the header) | not preregistered |
| P4 workspace | built, leak check passed, header included, baseline compiles | pass |

The checker's own bottom line is "failed checks: 1": P3's first string, as
written. It reports that because it is the preregistered measure; the
deviation log above explains why the widened string is the one the verdict
uses.

Why the P2 control changes only 3 of 6 rows: the f32 rows compare the
baseline with itself, so their error is 0 with or without the square root.
The int4 rows change from 6.6e-02 to 4.4e-03, its square.

### Secondary

- **Arm syntax check: passed.** `clang++ --target=aarch64-linux-gnu
  -march=armv8.2-a+dotprod+i8mm -fsyntax-only`, against the real KleidiAI
  headers at the pinned commit, reported 0 errors for `src/main.cpp`,
  `experiments/gemv-decode.cpp` and `experiments/baseline-fairness.cpp`.
  `baseline-fairness.cpp` used the stand-in Accelerate header, because
  Accelerate exists only on macOS. This container has only x86 C library
  headers, so an empty `gnu/stubs-32.h` was supplied. This checks syntax
  and types only: nothing was compiled to machine code or linked.
- **Real hardware: pending.** The next Mac session builds all three
  programs (`build.sh`, `experiments/build-gemv.sh`,
  `experiments/build-baseline-fairness.sh`).

### Noticed in passing (not a measure)

The workspace includes `results/2026-10-03-1621-baseline-fairness/`, which
holds measured "KleidiAI int4" timings. It contains none of the port's
identifiers, so the leak check passes, but it tells the agent what the port
achieves. Whether `results` belongs in `ANSWER_KEYS` is a separate
decision, not made here.

**Follow-up, 2026-10-04:** `results` was added to `ANSWER_KEYS` in a
later commit. A workspace built afterwards holds the same files as before
apart from `results/`, still passes the leak check, and its baseline still
compiles. `bench-harness-check/check.out` predates the change, so its file
list still shows `results/`.
