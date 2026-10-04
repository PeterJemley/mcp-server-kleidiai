// x86 test stand-ins for the KleidiAI functions gemv-decode.cpp calls. Packing
// stores floats (RHS dequantized from the int4 nibbles with its scales), and
// every matmul variant is a plain float GEMM, so outputs carry real error.
#include <cstring>
#include "kai_lhs_quant_pack_qai8dxp_f32.h"
#include "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0.h"
#include "kai_matmul_clamp_f32_qai8dxp1x4_qsi4cxp4x4_1x4_neon_dotprod.h"
#include "kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp4x8_1x4x32_neon_dotprod.h"
#include "kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp8x8_1x8x32_neon_dotprod.h"
#include "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.h"
static size_t g_k;
extern "C" {
size_t kai_get_lhs_packed_size_lhs_quant_pack_qai8dxp_f32(size_t m, size_t k, size_t, size_t, size_t) { return m * k * sizeof(float); }
void kai_run_lhs_quant_pack_qai8dxp_f32(size_t m, size_t k, size_t, size_t, size_t, size_t, const float* lhs, size_t, void* out) { std::memcpy(out, lhs, m * k * sizeof(float)); }
size_t kai_get_rhs_packed_size_rhs_pack_nxk_qsi4cxp_qs4cxs1s0(size_t n, size_t k, size_t, size_t, size_t) { return n * k * sizeof(float); }
void kai_run_rhs_pack_nxk_qsi4cxp_qs4cxs1s0(size_t, size_t n, size_t k, size_t, size_t, size_t, const uint8_t* rhs, const float*, const float* scale, void* out, size_t, const struct kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0_params* p) {
    float* f = static_cast<float*>(out); g_k = k;
    for (size_t in = 0; in < n; ++in) for (size_t ik = 0; ik < k; ++ik) {
        const uint8_t byte = rhs[in * (k / 2) + ik / 2];
        const int nib = (ik % 2 == 0) ? (byte & 0xF) : (byte >> 4);
        f[in * k + ik] = (nib - static_cast<int>(p->rhs_zero_point)) * scale[in];
    }
}
}
static void gemm(size_t m, size_t n, size_t k, const void* l, const void* r, float* dst, size_t stride) {
    const float* a = static_cast<const float*>(l); const float* b = static_cast<const float*>(r);
    for (size_t i = 0; i < m; ++i) for (size_t j = 0; j < n; ++j) {
        float acc = 0; for (size_t p = 0; p < k; ++p) acc += a[i * k + p] * b[j * k + p];
        dst[i * (stride / sizeof(float)) + j] = acc;
    }
}
#define STUB(V) extern "C" { \
  size_t kai_get_mr_matmul_clamp_f32_##V(void) { return 1; } size_t kai_get_nr_matmul_clamp_f32_##V(void) { return 8; } \
  size_t kai_get_kr_matmul_clamp_f32_##V(void) { return 8; } size_t kai_get_sr_matmul_clamp_f32_##V(void) { return 2; } \
  void kai_run_matmul_clamp_f32_##V(size_t m, size_t n, size_t k, const void* l, const void* r, float* d, size_t s, size_t, float, float) { gemm(m, n, k, l, r, d, s); } }
STUB(qai8dxp1x4_qsi4cxp4x4_1x4_neon_dotprod)
STUB(qai8dxp1x8_qsi4cxp4x8_1x4x32_neon_dotprod)
STUB(qai8dxp1x8_qsi4cxp8x8_1x8x32_neon_dotprod)
STUB(qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm)
