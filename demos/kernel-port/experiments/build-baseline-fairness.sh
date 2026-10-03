#!/bin/sh -e
# Builds the baseline-fairness experiment (see baseline-fairness.md). Same
# compiler flags as the published benchmark (build.sh), plus Accelerate.
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
    "$KAI_MATMUL/kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.c"; do
    $CC -O3 $ARCH -I "$KAI" -c "$src" -o "build/$(basename "$src" .c).o"
done

$CXX -O3 -ffast-math -std=c++17 $ARCH -DACCELERATE_NEW_LAPACK \
    -I "$KAI" -I "$KAI_PACK" -I "$KAI_MATMUL" -I src \
    experiments/baseline-fairness.cpp src/matmul_f32.cpp src/matmul_int4_kleidiai.cpp \
    build/kai_lhs_quant_pack_qai8dxp_f32.o \
    build/kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0.o \
    build/kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm.o \
    -framework Accelerate \
    -o build/baseline-fairness
echo "built build/baseline-fairness"
