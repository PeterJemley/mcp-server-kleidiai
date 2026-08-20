#include <cstddef>

// The kernel this demo ports: a plain f32 matmul as found in hand-rolled
// inference code. Weights (RHS) are row-major [N, K] — the layout llama-style
// engines keep them in — so each output is a contiguous dot product:
// dst[im][in] = dot(lhs[im][:], rhs[in][:]).
void matmul_f32(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst) {
    for (size_t im = 0; im < m; ++im) {
        const float* a = lhs + im * k;
        for (size_t in = 0; in < n; ++in) {
            const float* b = rhs + in * k;
            float acc = 0.0f;
            for (size_t ik = 0; ik < k; ++ik) {
                acc += a[ik] * b[ik];
            }
            dst[im * n + in] = acc;
        }
    }
}
