#!/bin/sh -e
# Flips this directory between the recording "before" state and the full
# rehearsed state. Requires a clean git tree so restore is always lossless.
#
#   ./demo-reset.sh before   — strip every answer key (rehearsal port, README
#                              recipe, recording plan) into .rehearsal/ and
#                              write a baseline-only harness + build script.
#                              The recorded agent must re-derive the port via
#                              the MCP server, not find it on disk.
#   ./demo-reset.sh restore  — put the rehearsed state back from git and
#                              remove .rehearsal/.
cd "$(dirname "$0")"

REPO_ROOT=$(git rev-parse --show-toplevel)
ANSWER_KEYS="src/matmul_int4_kleidiai.h src/matmul_int4_kleidiai.cpp README.md recording-plan.md"

case "${1:-}" in
before)
    if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
        echo "git tree not clean — commit or stash first so restore is lossless" >&2
        exit 1
    fi
    mkdir -p .rehearsal
    for f in $ANSWER_KEYS; do
        mkdir -p ".rehearsal/$(dirname "$f")"
        mv "$f" ".rehearsal/$f"
    done
    rm -rf build

    cat > src/main.cpp <<'CPP'
// Benchmark harness. matmul_f32 (src/matmul_f32.cpp) is the kernel to be
// ported; add the ported implementation alongside it, check it against the
// f32 result, and print a comparable row.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <random>
#include <vector>

void matmul_f32(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst);

namespace {

struct Shape {
    size_t m, n, k;
    const char* label;
};

// LLM-inference-shaped GEMMs: single-token decode, small batch, prompt chunk.
constexpr Shape kShapes[] = {
    {1, 4096, 4096, "decode (M=1)"},
    {32, 4096, 4096, "batch (M=32)"},
    {256, 4096, 4096, "prompt (M=256)"},
};

// Relative RMSE for checking a quantized port against the f32 result.
double rel_rmse(const float* ref, const float* got, size_t len) {
    double err = 0.0, mag = 0.0;
    for (size_t i = 0; i < len; ++i) {
        const double d = static_cast<double>(ref[i]) - got[i];
        err += d * d;
        mag += static_cast<double>(ref[i]) * ref[i];
    }
    return mag > 0.0 ? std::sqrt(err / mag) : std::sqrt(err / len);
}

template <typename Run>
double median_ms(double gflop, Run&& run) {
    run();
    const size_t reps = std::max<size_t>(5, std::min<size_t>(100, static_cast<size_t>(5.0 / gflop)));
    std::vector<double> samples;
    for (size_t r = 0; r < reps; ++r) {
        const auto t0 = std::chrono::steady_clock::now();
        run();
        const auto t1 = std::chrono::steady_clock::now();
        samples.push_back(std::chrono::duration<double, std::milli>(t1 - t0).count());
    }
    std::sort(samples.begin(), samples.end());
    return samples[samples.size() / 2];
}

}  // namespace

int main() {
    std::printf("| shape | impl | median ms | GFLOP/s | weights MB | rel RMSE |\n");
    std::printf("|---|---|---|---|---|---|\n");

    for (const Shape& s : kShapes) {
        std::mt19937 rng(42);
        std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
        std::vector<float> lhs(s.m * s.k), rhs(s.n * s.k), ref(s.m * s.n), dst(s.m * s.n);
        for (float& v : lhs) v = dist(rng);
        for (float& v : rhs) v = dist(rng);

        matmul_f32(s.m, s.n, s.k, lhs.data(), rhs.data(), ref.data());
        const double gflop = 2.0 * s.m * s.n * s.k / 1e9;

        const double f32_ms =
            median_ms(gflop, [&] { matmul_f32(s.m, s.n, s.k, lhs.data(), rhs.data(), dst.data()); });
        std::printf(
            "| %s | f32 baseline | %.3f | %.1f | %.1f | %.1e |\n", s.label, f32_ms,
            gflop / (f32_ms / 1e3), s.n * s.k * sizeof(float) / 1e6,
            rel_rmse(ref.data(), dst.data(), ref.size()));
    }
    return 0;
}
CPP

    cat > build.sh <<'SH'
#!/bin/sh -e
# Builds the benchmark. -ffast-math lets clang vectorize the baseline's dot
# loop (standard practice in inference engines).
cd "$(dirname "$0")"
CXX=${CXX:-clang++}
mkdir -p build
$CXX -O3 -ffast-math -std=c++17 -march=armv8.2-a+dotprod+i8mm \
    src/main.cpp src/matmul_f32.cpp \
    -o build/bench
echo "built build/bench"
SH
    chmod +x build.sh
    echo "before-state ready: answer keys in .rehearsal/, baseline-only harness in place"
    ;;
restore)
    git -C "$REPO_ROOT" checkout -- "$(pwd)"
    rm -rf .rehearsal build
    echo "rehearsed state restored from git"
    ;;
*)
    echo "usage: $0 before|restore" >&2
    exit 2
    ;;
esac
