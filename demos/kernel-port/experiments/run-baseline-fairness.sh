#!/bin/sh -e
# Runs the baseline-fairness experiment exactly as preregistered in
# baseline-fairness.md: refuses unless that plan is committed and the tree is
# clean, then builds, records the run manifest, makes five separate process
# runs, and writes the computed summary. Everything lands in
# results/<timestamp>-baseline-fairness/, ready to commit.
cd "$(dirname "$0")/.."

git ls-files --error-unmatch experiments/baseline-fairness.md >/dev/null 2>&1 || {
    echo "commit experiments/baseline-fairness.md before the first run" >&2
    exit 1
}
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "working tree has uncommitted changes; commit them so the run maps to one commit" >&2
    exit 1
fi

./experiments/build-baseline-fairness.sh

OUT=results/$(date +%Y-%m-%d-%H%M)-baseline-fairness
mkdir -p "$OUT"
{
    echo "repo_commit: $(git rev-parse HEAD)"
    echo "kleidiai_commit: $(git -C third_party/kleidiai rev-parse HEAD)"
    echo "machine: $(sysctl -n hw.model) / $(sysctl -n machdep.cpu.brand_string)"
    echo "macos: $(sw_vers -productVersion) ($(sw_vers -buildVersion))"
    echo "compiler: $(clang++ --version | head -1)"
    echo "power: $(pmset -g batt | head -1)"
    echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$OUT/manifest.txt"
cat "$OUT/manifest.txt"

for i in 1 2 3 4 5; do
    echo "run $i of 5"
    VECLIB_MAXIMUM_THREADS=1 ./build/baseline-fairness > "$OUT/run$i.md"
    sleep 10
done

python3 experiments/summarize_baseline_fairness.py "$OUT"/run*.md | tee "$OUT/summary.md"
echo "results in $OUT"
