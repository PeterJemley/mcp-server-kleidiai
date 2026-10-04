// Experiment: how much of the int4 port's batch/prompt speedup is weight reuse?
//
// The published baseline (src/matmul_f32.cpp) re-reads all N*K weights for
// every input row, so its bytes-per-FLOP is the same at M=1, 32 and 256,
// while the int4 kernel computes multi-row tiles that reuse each loaded
// weight. Questions, predictions and decision rules are in
// baseline-fairness.md, committed before the first run.
//
// Part "shapes" (the published shapes, N=K=4096): the published f32 loop;
// the same loop sharing each weight row across 4 and 8 input rows;
// Accelerate's cblas_sgemm, single-threaded; and the int4 port.
// Part "sweep" (M=32, K=4096, N=128..4096): the published loop and the
// 8-row loop with weights from 2 MB to 64 MB. Only N changes, so the inner
// loop is identical across the sweep and only the working set grows.
//
// Inputs match the published benchmark (src/main.cpp, seed 42). Every
// implementation is checked against the published loop's output, and the
// program exits non-zero if any check fails.

#include <Accelerate/Accelerate.h>

#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>

#include "bench_harness.h"
#include "matmul_int4_kleidiai.h"

void matmul_f32(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst);

namespace {

// Pass bars, fixed in baseline-fairness.md before the first run. The f32
// variants differ from the reference only in summation order; int4 is
// expected at 1/15 ~= 6.7e-2 for these uniform test weights.
constexpr double kF32Tolerance = 1e-4;
constexpr double kInt4Tolerance = 8e-2;

// One untimed warmup call, then repetitions until at least 10 runs and
// 1.5 s have accumulated (at most 200), so slow shapes get more timed runs
// than the published harness's 5.
constexpr bench::RepRule kRule{10, 200, 1500.0};

bool g_failed = false;

// The published loop with R input rows sharing each pass over a weight row,
// so every weight loaded serves R rows instead of one. Rows left over when
// M is not a multiple of R use the published loop.
template <size_t R>
void matmul_f32_rows(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst) {
    size_t im = 0;
    for (; im + R <= m; im += R) {
        for (size_t in = 0; in < n; ++in) {
            const float* b = rhs + in * k;
            float acc[R] = {};
            for (size_t ik = 0; ik < k; ++ik) {
                const float w = b[ik];
                for (size_t r = 0; r < R; ++r) {
                    acc[r] += lhs[(im + r) * k + ik] * w;
                }
            }
            for (size_t r = 0; r < R; ++r) {
                dst[(im + r) * n + in] = acc[r];
            }
        }
    }
    if (im < m) {
        matmul_f32(m - im, n, k, lhs + im * k, rhs, dst + im * n);
    }
}

void matmul_accelerate(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst) {
    cblas_sgemm(
        CblasRowMajor, CblasNoTrans, CblasTrans, static_cast<int>(m), static_cast<int>(n),
        static_cast<int>(k), 1.0f, lhs, static_cast<int>(k), rhs, static_cast<int>(k), 0.0f, dst,
        static_cast<int>(n));
}

struct Case {
    const char* part;
    size_t m, n, k;
    std::vector<float> lhs, rhs, ref, dst;
    double base_ms = 0.0;

    Case(const char* part_, size_t m_, size_t n_, size_t k_)
        : part(part_), m(m_), n(n_), k(k_), lhs(m_ * k_), rhs(n_ * k_), ref(m_ * n_), dst(m_ * n_) {
        std::mt19937 rng(42);
        std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
        for (float& v : lhs) v = dist(rng);
        for (float& v : rhs) v = dist(rng);
        matmul_f32(m, n, k, lhs.data(), rhs.data(), ref.data());
    }

    // Times one implementation and prints its row. dst is poisoned with NaN
    // first, so an implementation that skips any output fails its check
    // instead of inheriting the previous row's result.
    template <typename Run>
    void measure(const char* impl, size_t weight_bytes, double tolerance, Run&& run) {
        bench::poison(dst);
        const bench::Timing t = bench::time_ms(run, kRule);
        if (base_ms == 0.0) {
            base_ms = t.median_ms;
        }
        const double rmse = bench::rel_rmse(ref.data(), dst.data(), dst.size());
        const bool ok = bench::all_finite(dst) && rmse <= tolerance;
        g_failed |= !ok;
        const double gflop = 2.0 * m * n * k / 1e9;
        std::printf(
            "| %s | %zu | %zu | %zu | %s | %.3f | %.3f | %.3f | %.1f | %.1f | %.1e | %.2fx | %s |\n",
            part, m, n, k, impl, t.median_ms, t.min_ms, t.max_ms, gflop / (t.median_ms / 1e3),
            weight_bytes / 1e6, rmse, base_ms / t.median_ms, ok ? "ok" : "FAIL");
        std::fflush(stdout);
    }
};

}  // namespace

int main() {
    const char* threads = std::getenv("VECLIB_MAXIMUM_THREADS");
    if (threads == nullptr || std::strcmp(threads, "1") != 0) {
        std::fprintf(stderr, "set VECLIB_MAXIMUM_THREADS=1 so Accelerate runs single-threaded like every other row\n");
        return 2;
    }

    // The correctness check must be able to fail: identical outputs score 0,
    // a 1% perturbation must exceed the f32 bar, and poisoned (never-written)
    // output must be caught.
    {
        std::vector<float> a{1.0f, -2.0f, 3.0f, -4.0f}, b = a, p = a;
        for (float& v : b) v *= 1.01f;
        bench::poison(p);
        if (bench::rel_rmse(a.data(), a.data(), a.size()) != 0.0 ||
            bench::rel_rmse(a.data(), b.data(), b.size()) <= kF32Tolerance || !bench::all_finite(a) ||
            bench::all_finite(p)) {
            std::fprintf(stderr, "correctness check cannot fail; refusing to run\n");
            return 2;
        }
    }

    std::printf(
        "| part | M | N | K | impl | median ms | min ms | max ms | GFLOP/s | weights MB | rel RMSE | vs published f32 | check |\n");
    std::printf("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");

    for (size_t m : {size_t{1}, size_t{32}, size_t{256}}) {
        Case c("shapes", m, 4096, 4096);
        const float* a = c.lhs.data();
        const float* b = c.rhs.data();
        float* d = c.dst.data();
        const size_t f32_bytes = c.n * c.k * sizeof(float);
        c.measure("f32 published loop", f32_bytes, kF32Tolerance, [&] { matmul_f32(m, c.n, c.k, a, b, d); });
        c.measure("f32 4-row loop", f32_bytes, kF32Tolerance, [&] { matmul_f32_rows<4>(m, c.n, c.k, a, b, d); });
        c.measure("f32 8-row loop", f32_bytes, kF32Tolerance, [&] { matmul_f32_rows<8>(m, c.n, c.k, a, b, d); });
        c.measure("Accelerate sgemm", f32_bytes, kF32Tolerance, [&] { matmul_accelerate(m, c.n, c.k, a, b, d); });
        KleidiInt4Matmul int4(c.n, c.k, b);
        c.measure("KleidiAI int4", int4.weight_bytes(), kInt4Tolerance, [&] { int4.run(m, a, d); });
    }

    for (size_t n : {size_t{128}, size_t{256}, size_t{1024}, size_t{4096}}) {
        Case c("sweep", 32, n, 4096);
        const float* a = c.lhs.data();
        const float* b = c.rhs.data();
        float* d = c.dst.data();
        const size_t f32_bytes = c.n * c.k * sizeof(float);
        c.measure("f32 published loop", f32_bytes, kF32Tolerance, [&] { matmul_f32(c.m, n, c.k, a, b, d); });
        c.measure("f32 8-row loop", f32_bytes, kF32Tolerance, [&] { matmul_f32_rows<8>(c.m, n, c.k, a, b, d); });
    }

    if (g_failed) {
        std::fprintf(stderr, "a correctness check failed; this run's timings are void\n");
        return 1;
    }
    return 0;
}
