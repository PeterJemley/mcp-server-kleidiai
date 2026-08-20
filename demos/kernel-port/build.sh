#!/bin/sh -e
# Builds the benchmark: f32 baseline + KleidiAI int4 port. The kai micro-
# kernels are C (restrict) and compile as C; the harness is C++. -ffast-math
# lets clang vectorize the baseline's dot loop (standard practice in
# inference engines — the baseline should be a competent f32 kernel, not a
# strawman).
cd "$(dirname "$0")"

KAI=third_party/kleidiai
if [ ! -d "$KAI" ]; then
    echo "missing $KAI — run ./fetch_kleidiai.sh first" >&2
    exit 1
fi
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

$CXX -O3 -ffast-math -std=c++17 $ARCH \
    -I "$KAI" -I "$KAI_PACK" -I "$KAI_MATMUL" \
    src/main.cpp src/matmul_f32.cpp src/matmul_int4_kleidiai.cpp \
    build/*.o \
    -o build/bench
echo "built build/bench"
