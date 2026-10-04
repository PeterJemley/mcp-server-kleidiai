// Benchmark harness for the M3 kernel-port demo.
//
// "Before" is matmul_f32 (src/matmul_f32.cpp); "after" is the KleidiAI int4
// port (src/matmul_int4_kleidiai.cpp). Both run on the same inputs and are
// checked against the f32 result, so before/after is a single run. Weight
// quantization + packing is done once outside the timed region — weights are
// static in inference — while LHS dynamic quantization is timed on every run,
// exactly as it must happen at inference time.

#include <cstddef>
#include <cstdio>
#include <random>
#include <vector>

#include "bench_harness.h"
#include "matmul_int4_kleidiai.h"

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

// Relative RMSE against the f32 result. For uniform [-1,1] weights the int4
// quantization error is (range/15)/sqrt(12) against a weight RMS of
// range/(2*sqrt(3)) — an expected rel RMSE of ~6.7e-2, which the port matches
// to two digits. A wrong port (bad packing, wrong scales) shows O(1) error,
// not a few percent.
void print_row(
    const Shape& s, const char* impl, double ms, double base_ms, size_t weight_bytes, const float* ref,
    const float* got) {
    const double gflop = 2.0 * s.m * s.n * s.k / 1e9;
    std::printf(
        "| %s | %s | %.3f | %.1f | %.1f | %.1e | %.2fx |\n", s.label, impl, ms, gflop / (ms / 1e3),
        weight_bytes / 1e6, bench::rel_rmse(ref, got, s.m * s.n), base_ms / ms);
}

}  // namespace

int main() {
    std::printf("| shape | impl | median ms | GFLOP/s | weights MB | rel RMSE | speedup |\n");
    std::printf("|---|---|---|---|---|---|---|\n");

    for (const Shape& s : kShapes) {
        std::mt19937 rng(42);
        std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
        std::vector<float> lhs(s.m * s.k), rhs(s.n * s.k), ref(s.m * s.n), dst(s.m * s.n);
        for (float& v : lhs) v = dist(rng);
        for (float& v : rhs) v = dist(rng);

        matmul_f32(s.m, s.n, s.k, lhs.data(), rhs.data(), ref.data());
        const double gflop = 2.0 * s.m * s.n * s.k / 1e9;
        // Enough repetitions for stability without minute-long runs.
        const bench::RepRule rule = bench::fixed_for(gflop, 5, 100);

        const double f32_ms =
            bench::time_ms([&] { matmul_f32(s.m, s.n, s.k, lhs.data(), rhs.data(), dst.data()); }, rule).median_ms;
        print_row(s, "f32 baseline", f32_ms, f32_ms, s.n * s.k * sizeof(float), ref.data(), dst.data());

        KleidiInt4Matmul int4(s.n, s.k, rhs.data());
        const double int4_ms = bench::time_ms([&] { int4.run(s.m, lhs.data(), dst.data()); }, rule).median_ms;
        print_row(s, "KleidiAI int4 (i8mm)", int4_ms, f32_ms, int4.weight_bytes(), ref.data(), dst.data());
    }
    return 0;
}
