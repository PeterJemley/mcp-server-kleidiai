// Test stand-in for macOS Accelerate: a plain row-major sgemm, C = A x B^T only.
#pragma once
enum CBLAS_ORDER { CblasRowMajor = 101 };
enum CBLAS_TRANSPOSE { CblasNoTrans = 111, CblasTrans = 112 };
inline void cblas_sgemm(CBLAS_ORDER, CBLAS_TRANSPOSE ta, CBLAS_TRANSPOSE tb, int m, int n, int k, float alpha,
                        const float* a, int lda, const float* b, int ldb, float beta, float* c, int ldc) {
    if (ta != CblasNoTrans || tb != CblasTrans) __builtin_trap();
    for (int i = 0; i < m; ++i)
        for (int j = 0; j < n; ++j) {
            float acc = 0.0f;
            for (int p = 0; p < k; ++p) acc += a[i * lda + p] * b[j * ldb + p];
            c[i * ldc + j] = alpha * acc + beta * c[i * ldc + j];
        }
}
