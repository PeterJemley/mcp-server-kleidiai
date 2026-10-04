#pragma once

// Shared measurement code for the benchmark and its experiments: the timing
// loop, relative RMSE, and output checks that survive -ffast-math. Each
// program passes its own repetition rule, so one implementation serves rules
// that differ on purpose (experiments/bench-harness.md).

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <vector>

namespace bench {

// After one untimed warmup call, time at least min_reps calls and keep going
// while fewer than min_total_ms have accumulated, but never past max_reps.
struct RepRule {
    size_t min_reps;
    size_t max_reps;
    double min_total_ms;
};

// A fixed count sized to about 5 GFLOP of timed work, clamped to [lo, hi].
inline RepRule fixed_for(double gflop, size_t lo, size_t hi) {
    const size_t reps = std::max<size_t>(lo, std::min<size_t>(hi, static_cast<size_t>(5.0 / gflop)));
    return {reps, reps, 0.0};
}

struct Timing {
    double median_ms, min_ms, max_ms;
};

template <typename Clock = std::chrono::steady_clock, typename Run>
Timing time_ms(Run&& run, RepRule rule) {
    run();
    std::vector<double> samples;
    double total = 0.0;
    while (samples.size() < rule.max_reps && (samples.size() < rule.min_reps || total < rule.min_total_ms)) {
        const auto t0 = Clock::now();
        run();
        const auto t1 = Clock::now();
        samples.push_back(std::chrono::duration<double, std::milli>(t1 - t0).count());
        total += samples.back();
    }
    std::sort(samples.begin(), samples.end());
    return {samples[samples.size() / 2], samples.front(), samples.back()};
}

// Relative RMSE of got against ref; plain RMSE if ref is all zero.
inline double rel_rmse(const float* ref, const float* got, size_t len) {
    double err = 0.0, mag = 0.0;
    for (size_t i = 0; i < len; ++i) {
        const double d = static_cast<double>(ref[i]) - got[i];
        err += d * d;
        mag += static_cast<double>(ref[i]) * ref[i];
    }
    return mag > 0.0 ? std::sqrt(err / mag) : std::sqrt(err / len);
}

// -ffast-math lets the compiler assume floats are never NaN or infinite, so
// isnan() and NaN comparisons can be folded away. Poisoning and the
// finiteness check therefore work on bit patterns.
constexpr uint32_t kQuietNanBits = 0x7fc00000u;

inline void poison(std::vector<float>& v) {
    for (float& x : v) std::memcpy(&x, &kQuietNanBits, sizeof(x));
}

inline bool all_finite(const std::vector<float>& v) {
    for (const float& x : v) {
        uint32_t bits;
        std::memcpy(&bits, &x, sizeof(bits));
        if ((bits & 0x7f800000u) == 0x7f800000u) return false;
    }
    return true;
}

}  // namespace bench
