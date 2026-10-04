// Test stand-in for the KleidiAI port: same int4 per-channel recipe, float math.
#include "matmul_int4_kleidiai.h"
#include <cfloat>
#include <cmath>
#include <cstring>
static std::vector<float> g_deq;
KleidiInt4Matmul::KleidiInt4Matmul(size_t n, size_t k, const float* rhs) : n_(n), k_(k) {
    g_deq.assign(n * k, 0.0f);
    rhs_packed_.resize(n * k / 2 + n * 4);
    for (size_t in = 0; in < n; ++in) {
        float lo = FLT_MAX, hi = -FLT_MAX;
        for (size_t ik = 0; ik < k; ++ik) { lo = std::fmin(lo, rhs[in*k+ik]); hi = std::fmax(hi, rhs[in*k+ik]); }
        const float rmin = std::fmin(0.0f, lo), rmax = std::fmax(0.0f, hi);
        const float scale = rmin == rmax ? 1.0f : 15.0f / (rmax - rmin);
        for (size_t ik = 0; ik < k; ++ik) {
            int v = static_cast<int>(std::round(rhs[in*k+ik] * scale)); v = v < -8 ? -8 : (v > 7 ? 7 : v);
            g_deq[in*k+ik] = v / scale;
        }
    }
}
void KleidiInt4Matmul::run(size_t m, const float* lhs, float* dst) {
    for (size_t i = 0; i < m; ++i) for (size_t j = 0; j < n_; ++j) {
        float acc = 0.0f; for (size_t p = 0; p < k_; ++p) acc += lhs[i*k_+p] * g_deq[j*k_+p];
        dst[i*n_+j] = acc; }
}
