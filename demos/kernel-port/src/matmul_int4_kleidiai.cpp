#include "matmul_int4_kleidiai.h"

#include <cfloat>
#include <cmath>
#include <cstring>

#include "kai_lhs_quant_pack_qai8dxp_f32.h"
#include "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.h"
#include "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0.h"

namespace {

// f32 -> int4 symmetric per-channel quantization in the qs4cx native format
// the RHS pack kernel consumes: two nibbles per byte (even k low, odd k
// high), values stored offset by +8, one scale per output channel. Recipe
// follows KleidiAI's matmul_clamp_f32_qai8dxp_qsi4cxp example (Apache-2.0).
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
        const float rmin = std::fmin(0.0f, lo);
        const float rmax = std::fmax(0.0f, hi);
        const float scale = rmin == rmax ? 1.0f : 15.0f / (rmax - rmin);
        for (size_t ik = 0; ik < k; ++ik) {
            int32_t v = static_cast<int32_t>(std::round(src[ik] * scale));
            v = v < -8 ? -8 : (v > 7 ? 7 : v);
            const uint8_t nibble = static_cast<uint8_t>(v + 8);
            rhs_qs4cx[in * stride + ik / 2] |= (ik % 2 == 0) ? nibble : nibble << 4;
        }
        scales[in] = scale != 0.0f ? 1.0f / scale : 0.0f;
    }
}

}  // namespace

KleidiInt4Matmul::KleidiInt4Matmul(size_t n, size_t k, const float* rhs_f32) : n_(n), k_(k) {
    std::vector<uint8_t> rhs_qs4cx(n * (k / 2));
    std::vector<float> scales(n);
    quant_nxk_qs4cx(n, k, rhs_f32, rhs_qs4cx.data(), scales.data());

    const size_t nr = kai_get_nr_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm();
    const size_t kr = kai_get_kr_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm();
    const size_t sr = kai_get_sr_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm();
    rhs_packed_.resize(kai_get_rhs_packed_size_rhs_pack_nxk_qsi4cxp_qs4cxs1s0(n, k, nr, kr, sr));

    kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0_params params;
    params.lhs_zero_point = 1;
    params.rhs_zero_point = 8;
    kai_run_rhs_pack_nxk_qsi4cxp_qs4cxs1s0(
        1, n, k, nr, kr, sr, rhs_qs4cx.data(), /*bias=*/nullptr, scales.data(), rhs_packed_.data(),
        /*extra_bytes=*/0, &params);
}

void KleidiInt4Matmul::run(size_t m, const float* lhs_f32, float* dst) {
    const size_t mr = kai_get_mr_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm();
    const size_t kr = kai_get_kr_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm();
    const size_t sr = kai_get_sr_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm();

    const size_t lhs_packed_size = kai_get_lhs_packed_size_lhs_quant_pack_qai8dxp_f32(m, k_, mr, kr, sr);
    if (lhs_packed_.size() < lhs_packed_size) {
        lhs_packed_.resize(lhs_packed_size);
    }
    kai_run_lhs_quant_pack_qai8dxp_f32(
        m, k_, mr, kr, sr, /*m_idx_start=*/0, lhs_f32, k_ * sizeof(float), lhs_packed_.data());

    kai_run_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm(
        m, n_, k_, lhs_packed_.data(), rhs_packed_.data(), dst, /*dst_stride_row=*/n_ * sizeof(float),
        /*dst_stride_col=*/sizeof(float), -FLT_MAX, FLT_MAX);
}
