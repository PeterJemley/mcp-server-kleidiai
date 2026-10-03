"""Summarize baseline-fairness runs and apply the preregistered decision rules.

Reads the per-run tables written by build/baseline-fairness and computes every
number in the summary from them; nothing is typed in. The rules and
thresholds are the ones fixed in baseline-fairness.md before the first run.

Run: python3 experiments/summarize_baseline_fairness.py results/<dir>/run*.md
"""

from __future__ import annotations

import statistics
import sys

# The published rehearsal numbers this experiment links back to
# (demos/kernel-port/README.md, 2026-08-20).
PUBLISHED_F32_GFLOPS = {1: 35.3, 32: 35.4, 256: 35.0}
PUBLISHED_INT4_SPEEDUP = {1: 2.36, 32: 12.62, 256: 13.50}
LINK_TOLERANCE = 0.10

PUB = "f32 published loop"
ROW4 = "f32 4-row loop"
ROW8 = "f32 8-row loop"
ACC = "Accelerate sgemm"
INT4 = "KleidiAI int4"


def parse(path: str) -> dict[tuple[str, int, int, int, str], tuple[float, str]]:
    """Map (part, M, N, K, impl) to (median ms, check) for one run file."""
    rows = {}
    with open(path) as fh:
        for line in fh:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 13 or cells[0] not in ("shapes", "sweep"):
                continue
            key = (cells[0], int(cells[1]), int(cells[2]), int(cells[3]), cells[4])
            rows[key] = (float(cells[5]), cells[12])
    return rows


def gflops(key: tuple[str, int, int, int, str], ms: float) -> float:
    _, m, n, k, _ = key
    return 2.0 * m * n * k / 1e9 / (ms / 1e3)


def fmt_runs(values: list[float], spec: str = ".2f") -> str:
    return ", ".join(format(v, spec) for v in values)


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    runs = [parse(p) for p in paths]
    keys = sorted(set().union(*runs), key=lambda k: (k[0] != "shapes", k[1], k[2], k[4]))
    print(f"# Baseline-fairness summary ({len(runs)} run{'s' if len(runs) != 1 else ''})\n")
    if len(runs) != 5:
        print(f"**Note:** the plan calls for 5 runs; {len(runs)} found.\n")

    failed = [(p, key) for p, run in zip(paths, runs) for key, (_, check) in run.items() if check != "ok"]
    missing = [(p, key) for p, run in zip(paths, runs) for key in keys if key not in run]
    if failed or missing:
        print("**VOID: a correctness check failed or a run is incomplete.**\n")
        for p, key in failed:
            print(f"- FAIL in {p}: {key}")
        for p, key in missing:
            print(f"- missing in {p}: {key}")
        return 1

    def ms(run: dict, part: str, m: int, n: int, impl: str) -> float:
        return run[(part, m, n, 4096, impl)][0]

    print("## Every row: median across runs (range of the per-run medians)\n")
    print("| part | M | N | impl | median ms | range ms | GFLOP/s |")
    print("|---|---|---|---|---|---|---|")
    for key in keys:
        values = [run[key][0] for run in runs]
        med = statistics.median(values)
        print(f"| {key[0]} | {key[1]} | {key[2]} | {key[4]} | {med:.3f} | "
              f"{min(values):.3f}–{max(values):.3f} | {gflops(key, med):.1f} |")

    print("\n## Controls\n")
    linked = True
    for m in (1, 32, 256):
        g = statistics.median(gflops(("shapes", m, 4096, 4096, PUB), ms(r, "shapes", m, 4096, PUB)) for r in runs)
        s = statistics.median(ms(r, "shapes", m, 4096, PUB) / ms(r, "shapes", m, 4096, INT4) for r in runs)
        g_ok = abs(g / PUBLISHED_F32_GFLOPS[m] - 1) <= LINK_TOLERANCE
        s_ok = abs(s / PUBLISHED_INT4_SPEEDUP[m] - 1) <= LINK_TOLERANCE
        linked &= g_ok and s_ok
        print(f"- Link to the published table, M={m}: f32 {g:.1f} GFLOP/s vs {PUBLISHED_F32_GFLOPS[m]} "
              f"({'within' if g_ok else 'OUTSIDE'} ±10%); int4 speedup {s:.2f}x vs {PUBLISHED_INT4_SPEEDUP[m]}x "
              f"({'within' if s_ok else 'OUTSIDE'} ±10%)")
    for impl in (ROW4, ROW8):
        ratio = statistics.median(ms(r, "shapes", 1, 4096, impl) / ms(r, "shapes", 1, 4096, PUB) for r in runs)
        ok = abs(ratio - 1) <= LINK_TOLERANCE
        print(f"- M=1 fallback control: {impl} takes {ratio:.2f}x the published loop's time "
              f"({'within' if ok else 'OUTSIDE'} ±10%; it runs the same code at M=1)")
    if not linked:
        print("\n**NOT COMPARABLE TO THE README:** the published rows did not reproduce within ±10%, so the "
              "machine or toolchain differs from the published run. The outcomes below describe this run only.")

    print("\n## Q1 — is the published f32 loop compute-limited or memory-limited at N=K=4096?\n")
    r_runs = [max(gflops(("sweep", 32, n, 4096, PUB), ms(r, "sweep", 32, n, PUB)) for n in (128, 256))
              / gflops(("sweep", 32, 4096, 4096, PUB), ms(r, "sweep", 32, 4096, PUB)) for r in runs]
    r = statistics.median(r_runs)
    if r >= 1.5:
        verdict = "MEMORY-LIMITED — the 'compute ceiling' reading is refuted"
    elif 0.85 <= r <= 1.15:
        verdict = "COMPUTE-LIMITED — the 'compute ceiling' reading stands"
    else:
        verdict = "INCONCLUSIVE — between the two predictions"
    print(f"R = GFLOP/s with weights in cache (best of N=128, 256) ÷ GFLOP/s at N=4096 = **{r:.2f}** "
          f"(per run: {fmt_runs(r_runs)})\n\nVerdict: **{verdict}**")

    print("\n## Q2 — how much of the int4 speedup survives a reuse-matched f32 loop?\n")
    for m, role in ((256, "primary"), (32, "secondary")):
        s_pub = [ms(r_, "shapes", m, 4096, PUB) / ms(r_, "shapes", m, 4096, INT4) for r_ in runs]
        s_reuse = [min(ms(r_, "shapes", m, 4096, ROW4), ms(r_, "shapes", m, 4096, ROW8))
                   / ms(r_, "shapes", m, 4096, INT4) for r_ in runs]
        share = statistics.median(a / b for a, b in zip(s_reuse, s_pub))
        verdict = ("headline stands; reuse explains under 20% of it" if share >= 0.8 else
                   "restate the headline against the reuse-matched f32 loop; give the published-loop figure second")
        print(f"- M={m} ({role}): vs published loop **{statistics.median(s_pub):.2f}x**, "
              f"vs best of 4-/8-row loop **{statistics.median(s_reuse):.2f}x**; "
              f"share surviving **{share:.2f}** → {verdict}")

    print("\n## Secondary (exploratory, no prediction): int4 vs Accelerate sgemm, single-threaded\n")
    for m in (1, 32, 256):
        s = [ms(r_, "shapes", m, 4096, ACC) / ms(r_, "shapes", m, 4096, INT4) for r_ in runs]
        med = statistics.median(s)
        note = " — Accelerate f32 is faster than the int4 port here" if med < 1 else ""
        print(f"- M={m}: int4 is {med:.2f}x Accelerate's speed (per run: {fmt_runs(s)}){note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
