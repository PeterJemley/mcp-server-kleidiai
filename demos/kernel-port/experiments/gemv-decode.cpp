// Experiment: does a dedicated GEMV variant close the decode gap?
//
// Tests the explanation in docs/workbook.md Q30 for why the int4 port gains only
// 2.36x at M=1 vs ~13x at M>=32: the incumbent kernel is a GEMM variant with
// an 8-row output tile that M=1 cannot amortize. Prediction, stated before
// running (recorded in the session log and results table): a 1-row-tile GEMV
// variant is materially (>=1.5x) faster than the GEMM variant at M=1, and
// LOSES to it at M=32. Refutation condition: GEMV within ~10% of the GEMM
// variant at M=1.
//
// Protocol matches the demo benchmark: RHS quantize+pack per variant is
// untimed (weights are static); LHS quant+pack runs inside the timed region
// (activations change per call); LHS pack is also timed alone to decompose
// the per-call cost. Every variant is checked against the f32 reference.

#include <algorithm>
#include <cfloat>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

#include "kai_lhs_quant_pack_qai8dxp_f32.h"
#include "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0.h"

#include "kai_matmul_clamp_f32_qai8dxp1x4_qsi4cxp4x4_1x4_neon_dotprod.h"
#include "kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp4x8_1x4x32_neon_dotprod.h"
#include "kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp8x8_1x8x32_neon_dotprod.h"
#include "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.h"

void matmul_f32(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst);

namespace {

using MatmulFn = void (*)(
    size_t, size_t, size_t, const void*, const void*, float*, size_t, size_t, float, float);

struct Variant {
    const char* name;
    const char* kind;  // "GEMM" or "GEMV"
    size_t mr, nr, kr, sr;
    MatmulFn run;
};

#define VARIANT(short_name, kind, V)                                                      \
    Variant {                                                                             \
        short_name, kind, kai_get_mr_matmul_clamp_f32_##V(),                              \
            kai_get_nr_matmul_clamp_f32_##V(), kai_get_kr_matmul_clamp_f32_##V(),         \
            kai_get_sr_matmul_clamp_f32_##V(), kai_run_matmul_clamp_f32_##V               \
    }

// f32 -> int4 per-channel qs4cx quantization (same recipe as the port).
void quant_nxk_qs4cx(size_t n, size_t k, const float* rhs_f32, uint8_t* rhs_qs4cx, float* scales) {
    const size_t stride = k / 2;
    std::memset(rhs_qs4cx, 0, n * stride);
    for (size_t in = 0; in < n; ++in) {
        const float* src = rhs_f32 + in * k;
        float lo = FLT_MAX, hi = -FLT_MAX;
        for (size_t ik = 0; ik < k; ++ik) {
            lo = std::fmin(lo, src[ik]);
            hi = std::fmax(hi, src[ik]);
        }
        const float rmin = std::fmin(0.0f, lo), rmax = std::fmax(0.0f, hi);
        const float scale = rmin == rmax ? 1.0f : 15.0f / (rmax - rmin);
        for (size_t ik = 0; ik < k; ++ik) {
            int32_t v = static_cast<int32_t>(std::round(src[ik] * scale));
            v = v < -8 ? -8 : (v > 7 ? 7 : v);
            rhs_qs4cx[in * stride + ik / 2] |=
                (ik % 2 == 0) ? static_cast<uint8_t>(v + 8) : static_cast<uint8_t>(v + 8) << 4;
        }
        scales[in] = scale != 0.0f ? 1.0f / scale : 0.0f;
    }
}

double rel_rmse(const float* ref, const float* got, size_t len) {
    double err = 0.0, mag = 0.0;
    for (size_t i = 0; i < len; ++i) {
        const double d = static_cast<double>(ref[i]) - got[i];
        err += d * d;
        mag += static_cast<double>(ref[i]) * ref[i];
    }
    return std::sqrt(err / mag);
}

template <typename Run>
double median_ms(size_t reps, Run&& run) {
    run();
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
    const size_t n = 4096, k = 4096;
    const Variant variants[] = {
        VARIANT("8x8x32_neon_i8mm (incumbent)", "GEMM", qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm),
        VARIANT("1x8x32_neon_dotprod", "GEMV", qai8dxp1x8_qsi4cxp8x8_1x8x32_neon_dotprod),
        VARIANT("1x4x32_neon_dotprod", "GEMV", qai8dxp1x8_qsi4cxp4x8_1x4x32_neon_dotprod),
        VARIANT("1x4_neon_dotprod", "GEMV", qai8dxp1x4_qsi4cxp4x4_1x4_neon_dotprod),
    };

    std::mt19937 rng(42);
    std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
    std::vector<float> rhs(n * k);
    for (float& v : rhs) v = dist(rng);
    std::vector<uint8_t> rhs_qs4cx(n * (k / 2));
    std::vector<float> scales(n);
    quant_nxk_qs4cx(n, k, rhs.data(), rhs_qs4cx.data(), scales.data());

    std::printf("| M | variant | kind | total ms | lhs-pack ms | GFLOP/s | rel RMSE | vs f32 |\n");
    std::printf("|---|---|---|---|---|---|---|---|\n");

    for (size_t m : {size_t{1}, size_t{32}}) {
        std::vector<float> lhs(m * k), ref(m * n), dst(m * n);
        for (float& v : lhs) v = dist(rng);
        matmul_f32(m, n, k, lhs.data(), rhs.data(), ref.data());
        const double gflop = 2.0 * m * n * k / 1e9;
        const size_t reps = std::max<size_t>(20, std::min<size_t>(200, static_cast<size_t>(5.0 / gflop)));

        const double f32_ms =
            median_ms(reps, [&] { matmul_f32(m, n, k, lhs.data(), rhs.data(), dst.data()); });
        std::printf(
            "| %zu | f32 baseline | — | %.3f | — | %.1f | 0 | 1.00x |\n", m, f32_ms,
            gflop / (f32_ms / 1e3));

        for (const Variant& v : variants) {
            std::vector<uint8_t> rhs_packed(
                kai_get_rhs_packed_size_rhs_pack_nxk_qsi4cxp_qs4cxs1s0(n, k, v.nr, v.kr, v.sr));
            kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0_params params;
            params.lhs_zero_point = 1;
            params.rhs_zero_point = 8;
            kai_run_rhs_pack_nxk_qsi4cxp_qs4cxs1s0(
                1, n, k, v.nr, v.kr, v.sr, rhs_qs4cx.data(), nullptr, scales.data(),
                rhs_packed.data(), 0, &params);

            std::vector<uint8_t> lhs_packed(
                kai_get_lhs_packed_size_lhs_quant_pack_qai8dxp_f32(m, k, v.mr, v.kr, v.sr));

            auto lhs_pack = [&] {
                kai_run_lhs_quant_pack_qai8dxp_f32(
                    m, k, v.mr, v.kr, v.sr, 0, lhs.data(), k * sizeof(float), lhs_packed.data());
            };
            const double pack_ms = median_ms(reps, lhs_pack);
            const double total_ms = median_ms(reps, [&] {
                lhs_pack();
                v.run(
                    m, n, k, lhs_packed.data(), rhs_packed.data(), dst.data(), n * sizeof(float),
                    sizeof(float), -FLT_MAX, FLT_MAX);
            });
            std::printf(
                "| %zu | %s | %s | %.3f | %.3f | %.1f | %.1e | %.2fx |\n", m, v.name, v.kind,
                total_ms, pack_ms, gflop / (total_ms / 1e3), rel_rmse(ref.data(), dst.data(), m * n),
                f32_ms / total_ms);
        }
    }
    return 0;
}
