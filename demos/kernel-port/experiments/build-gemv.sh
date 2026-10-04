#!/bin/sh -e
# Builds the GEMV-vs-GEMM decode experiment (see gemv-decode.cpp header).
cd "$(dirname "$0")/.."

KAI=third_party/kleidiai
[ -d "$KAI" ] || { echo "run ../fetch_kleidiai.sh first" >&2; exit 1; }
KAI_PACK=$KAI/kai/ukernels/matmul/pack
KAI_MATMUL=$KAI/kai/ukernels/matmul/matmul_clamp_f32_qai8dxp_qsi4cxp

CC=${CC:-clang}
CXX=${CXX:-clang++}
ARCH="-march=armv8.2-a+dotprod+i8mm"
mkdir -p build

for src in \
    "$KAI_PACK/kai_lhs_quant_pack_qai8dxp_f32.c" \
    "$KAI_PACK/kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0.c" \
    "$KAI_MATMUL/kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.c" \
    "$KAI_MATMUL/kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp8x8_1x8x32_neon_dotprod.c" \
    "$KAI_MATMUL/kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp4x8_1x4x32_neon_dotprod.c" \
    "$KAI_MATMUL/kai_matmul_clamp_f32_qai8dxp1x4_qsi4cxp4x4_1x4_neon_dotprod.c"; do
    $CC -O3 $ARCH -I "$KAI" -c "$src" -o "build/$(basename "$src" .c).o"
done

$CXX -O3 -ffast-math -std=c++17 $ARCH \
    -I "$KAI" -I "$KAI_PACK" -I "$KAI_MATMUL" -I src \
    experiments/gemv-decode.cpp src/matmul_f32.cpp \
    build/kai_lhs_quant_pack_qai8dxp_f32.o \
    build/kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0.o \
    build/kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.o \
    build/kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp8x8_1x8x32_neon_dotprod.o \
    build/kai_matmul_clamp_f32_qai8dxp1x8_qsi4cxp4x8_1x4x32_neon_dotprod.o \
    build/kai_matmul_clamp_f32_qai8dxp1x4_qsi4cxp4x4_1x4_neon_dotprod.o \
    -o build/gemv-decode
echo "built build/gemv-decode"
