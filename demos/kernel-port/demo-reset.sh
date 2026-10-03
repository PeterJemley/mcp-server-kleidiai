#!/bin/sh -e
# Builds the workspace for the recorded kernel-port session, in which the
# agent must re-derive the int4 port through the MCP server rather than find
# it on disk:
#
#   ./demo-reset.sh workspace <dir>
#
# <dir> must be new and outside this repo. It becomes a git repository whose
# only commit is the baseline: the f32 kernel, a baseline-only harness and
# build script, and (ignored) the KleidiAI checkout, plus an .mcp.json that
# registers the server. The answer keys (rehearsal port, README recipe,
# recording plan, experiments) never enter it, nor does this repo's history,
# and the build refuses if any of the port's identifiers survive.
CALLER_PWD=$(pwd)
cd "$(dirname "$0")"

REPO_ROOT=$(git rev-parse --show-toplevel)
ANSWER_KEYS="src/matmul_int4_kleidiai.h src/matmul_int4_kleidiai.cpp README.md recording-plan.md experiments"

case "${1:-}" in
workspace)
    dest=${2:?"usage: $0 workspace <new-directory>"}
    case "$dest" in
    /*) ;;
    *) dest="$CALLER_PWD/$dest" ;;
    esac
    if [ -e "$dest" ]; then
        echo "$dest already exists — give a new directory" >&2
        exit 1
    fi
    if ! git -C "$REPO_ROOT" diff --quiet || ! git -C "$REPO_ROOT" diff --cached --quiet; then
        echo "git tree not clean — commit or stash first: the workspace is built from HEAD" >&2
        exit 1
    fi
    mkdir -p "$dest"
    dest=$(cd "$dest" && pwd -P)
    case "$dest/" in
    "$(cd "$REPO_ROOT" && pwd -P)"/*)
        rmdir "$dest"
        echo "the workspace must be outside this repo, or the agent finds the port one directory up" >&2
        exit 1
        ;;
    esac
    # A half-built workspace must never be mistaken for a finished one.
    trap 'rm -rf "$dest"' EXIT

    git -C "$REPO_ROOT" archive "HEAD:$(git rev-parse --show-prefix)" | tar -x -C "$dest"
    (cd "$dest" && rm -rf $ANSWER_KEYS demo-reset.sh .gitkeep)
    # Baseline-only harness and build script: the agent's starting point.
    cat > "$dest/src/main.cpp" <<'CPP'
// Benchmark harness. matmul_f32 (src/matmul_f32.cpp) is the kernel to be
// ported; add the ported implementation alongside it, check it against the
// f32 result, and print a comparable row.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <random>
#include <vector>

void matmul_f32(size_t m, size_t n, size_t k, const float* lhs, const float* rhs, float* dst);

namespace {

struct Shape {
    size_t m, n, k;
    const char* label;
};

// LLM-inference-shaped GEMMs: single-token decode, small batch, prompt chunk.
constexpr Shape kShapes[] = {
    {1, 4096, 4096, "decode (M=1)"},
    {32, 4096, 4096, "batch (M=32)"},
    {256, 4096, 4096, "prompt (M=256)"},
};

// Relative RMSE for checking a quantized port against the f32 result.
double rel_rmse(const float* ref, const float* got, size_t len) {
    double err = 0.0, mag = 0.0;
    for (size_t i = 0; i < len; ++i) {
        const double d = static_cast<double>(ref[i]) - got[i];
        err += d * d;
        mag += static_cast<double>(ref[i]) * ref[i];
    }
    return mag > 0.0 ? std::sqrt(err / mag) : std::sqrt(err / len);
}

template <typename Run>
double median_ms(double gflop, Run&& run) {
    run();
    const size_t reps = std::max<size_t>(5, std::min<size_t>(100, static_cast<size_t>(5.0 / gflop)));
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
    std::printf("| shape | impl | median ms | GFLOP/s | weights MB | rel RMSE |\n");
    std::printf("|---|---|---|---|---|---|\n");

    for (const Shape& s : kShapes) {
        std::mt19937 rng(42);
        std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
        std::vector<float> lhs(s.m * s.k), rhs(s.n * s.k), ref(s.m * s.n), dst(s.m * s.n);
        for (float& v : lhs) v = dist(rng);
        for (float& v : rhs) v = dist(rng);

        matmul_f32(s.m, s.n, s.k, lhs.data(), rhs.data(), ref.data());
        const double gflop = 2.0 * s.m * s.n * s.k / 1e9;

        const double f32_ms =
            median_ms(gflop, [&] { matmul_f32(s.m, s.n, s.k, lhs.data(), rhs.data(), dst.data()); });
        std::printf(
            "| %s | f32 baseline | %.3f | %.1f | %.1f | %.1e |\n", s.label, f32_ms,
            gflop / (f32_ms / 1e3), s.n * s.k * sizeof(float) / 1e6,
            rel_rmse(ref.data(), dst.data(), ref.size()));
    }
    return 0;
}
CPP

    cat > "$dest/build.sh" <<'SH'
#!/bin/sh -e
# Builds the benchmark. -ffast-math lets clang vectorize the baseline's dot
# loop (standard practice in inference engines).
cd "$(dirname "$0")"
CXX=${CXX:-clang++}
mkdir -p build
$CXX -O3 -ffast-math -std=c++17 -march=armv8.2-a+dotprod+i8mm \
    src/main.cpp src/matmul_f32.cpp \
    -o build/bench
echo "built build/bench"
SH
    chmod +x "$dest/build.sh"

    if [ -d third_party/kleidiai ]; then
        cp -R third_party "$dest/"
    fi
    "$dest/fetch_kleidiai.sh"

    server_python="$REPO_ROOT/packages/server-py/.venv/bin/python"
    if [ ! -x "$server_python" ]; then
        echo "warning: $server_python is missing — set up the server venv (root README) before recording" >&2
    fi
    cat > "$dest/.mcp.json" <<JSON
{
  "mcpServers": {
    "kleidiai": {
      "command": "$server_python",
      "args": ["-m", "mcp_server_kleidiai"]
    }
  }
}
JSON

    # The port's identifiers. KleidiAI's own checkout legitimately contains
    # them; nothing else in the workspace may. (Options precede the operands:
    # macOS grep stops parsing options at the first operand.)
    leaks=$(grep -rlE --exclude-dir=third_party --exclude-dir=.git \
        'matmul_int4_kleidiai|KleidiInt4Matmul|quant_nxk|qsi4c|qai8d|rhs_zero_point|kai_(run|get)_' \
        "$dest" || true)
    if [ -n "$leaks" ]; then
        echo "the port's identifiers survive in the workspace — not fit for recording:" >&2
        echo "$leaks" >&2
        exit 1
    fi

    git -C "$dest" init -q
    git -C "$dest" add -A
    git -C "$dest" commit -q -m "Baseline: f32 matmul and benchmark harness"
    trap - EXIT
    echo "workspace ready: $dest"
    echo "  one commit, no history; no answer-key identifiers outside third_party/"
    echo "  MCP server registered in .mcp.json: $server_python -m mcp_server_kleidiai"
    echo "  next: cd \"$dest\" && ./build.sh && ./build/bench, then start the agent there"
    ;;
*)
    echo "usage: $0 workspace <new-directory>" >&2
    exit 2
    ;;
esac
