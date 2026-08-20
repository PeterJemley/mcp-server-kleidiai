#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

// The ported kernel: f32 x int4 matmul via KleidiAI's qai8dxp/qsi4cxp
// micro-kernels, i8mm variant (kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_
// 8x8x32_neon_i8mm). Weights are quantized to int4 per-channel and packed
// once at construction — they are static in inference — while each run()
// dynamically quantizes and packs the LHS before multiplying, per the
// KleidiAI qsi4cx guide. Requires k to be a multiple of 8.
class KleidiInt4Matmul {
public:
    // rhs_f32 is [n, k] row-major, the same layout matmul_f32 consumes.
    KleidiInt4Matmul(size_t n, size_t k, const float* rhs_f32);

    // dst = lhs x rhs^T, lhs is [m, k] row-major, dst is [m, n] row-major.
    void run(size_t m, const float* lhs_f32, float* dst);

    // Bytes of packed weights read per matmul (vs n*k*4 for f32).
    size_t weight_bytes() const { return rhs_packed_.size(); }

private:
    size_t n_;
    size_t k_;
    std::vector<uint8_t> rhs_packed_;
    std::vector<uint8_t> lhs_packed_;  // scratch, sized on first run()
};
