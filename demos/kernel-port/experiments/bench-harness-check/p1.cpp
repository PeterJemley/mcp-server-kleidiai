// bench-harness.md P1: the shared harness against the old copies, extracted
// verbatim from the preregistration commit. Exit code = number of failed checks.
#include <chrono>
#include <cstdio>
#include <random>
#include <thread>

#include "bench_harness.h"
#include "old_extracted.h"

namespace {

int failures = 0;

void check(bool ok, const char* what) {
    if (!ok) ++failures;
    std::printf("  %-4s %s\n", ok ? "ok" : "FAIL", what);
}

struct FakeClock {
    using duration = std::chrono::steady_clock::duration;
    using rep = duration::rep;
    using period = duration::period;
    using time_point = std::chrono::time_point<FakeClock, duration>;
    static constexpr bool is_steady = true;
    static inline duration t{0};
    static time_point now() { return time_point(t); }
    static void advance_ms(double ms) {
        t += std::chrono::duration_cast<duration>(std::chrono::duration<double, std::milli>(ms));
    }
};

// Control: the shared loop, but reporting samples[0] as the median.
template <typename Clock, typename Run>
bench::Timing bad_median_time_ms(Run&& run, bench::RepRule rule) {
    bench::Timing t = bench::time_ms<Clock>(run, rule);
    t.median_ms = t.min_ms;
    return t;
}

template <typename TimeFn>
bool scripted(TimeFn time_fn, std::vector<double> script, bench::RepRule rule, double median, double lo, double hi,
              size_t expect_reps) {
    size_t i = 0;
    auto run = [&] { FakeClock::advance_ms(script[i++]); };
    const bench::Timing t = time_fn(run, rule);
    return t.median_ms == median && t.min_ms == lo && t.max_ms == hi && i == expect_reps + 1;
}

}  // namespace

int main() {
    std::printf("P1a fixed rules: calls to run() (warmup + timed), old copy vs shared harness\n");
    for (double gflop : {0.001, 0.0336, 1.07, 8.59, 100.0}) {
        size_t om = 0, ot = 0, og = 0, nm = 0, ng = 0, ctrl = 0;
        old_main::median_ms(gflop, [&] { ++om; });
        old_tmpl::median_ms(gflop, [&] { ++ot; });
        old_gemv::median_ms(old_gemv::reps_for(gflop), [&] { ++og; });
        bench::time_ms([&] { ++nm; }, bench::fixed_for(gflop, 5, 100));
        bench::time_ms([&] { ++ng; }, bench::fixed_for(gflop, 20, 200));
        bench::RepRule off = bench::fixed_for(gflop, 5, 100);
        ++off.min_reps;
        ++off.max_reps;
        bench::time_ms([&] { ++ctrl; }, off);
        char what[160];
        std::snprintf(what, sizeof what, "gflop %-7g main %zu/%zu  template %zu/%zu  gemv %zu/%zu  [control off-by-one %zu, must differ]",
                      gflop, om, nm, ot, nm, og, ng, ctrl);
        check(om == nm && ot == nm && og == ng && ctrl != om, what);
    }

    std::printf("P1b time-based rule (>=10 reps and >=1.5 s, <=200): calls to run()\n");
    for (int sleep_ms : {0, 120, 200}) {
        size_t o = 0, n = 0;
        auto work = [&](size_t& c) {
            ++c;
            if (sleep_ms) std::this_thread::sleep_for(std::chrono::milliseconds(sleep_ms));
        };
        old_fair::time_ms([&] { work(o); });
        bench::time_ms([&] { work(n); }, bench::RepRule{10, 200, 1500.0});
        char what[96];
        std::snprintf(what, sizeof what, "%3d ms per call: old %zu, shared %zu", sleep_ms, o, n);
        check(o == n, what);
    }

    std::printf("P1c rel_rmse: shared vs each old copy, identical values\n");
    std::mt19937 rng(7);
    std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
    bool same = true;
    for (int trial = 0; trial < 5; ++trial) {
        std::vector<float> ref(4096), got(4096);
        for (size_t i = 0; i < ref.size(); ++i) {
            ref[i] = dist(rng);
            got[i] = ref[i] + 0.05f * dist(rng);
        }
        const double v = bench::rel_rmse(ref.data(), got.data(), ref.size());
        same &= v == old_main::rel_rmse(ref.data(), got.data(), ref.size());
        same &= v == old_tmpl::rel_rmse(ref.data(), got.data(), ref.size());
        same &= v == old_gemv::rel_rmse(ref.data(), got.data(), ref.size());
        same &= v == old_fair::rel_rmse(ref.data(), got.data(), ref.size());
    }
    check(same, "5 random trials x 4 old copies: bit-identical");
    std::vector<float> zero(8, 0.0f), off(8, 0.5f);
    check(bench::rel_rmse(zero.data(), off.data(), 8) == 0.5,
          "all-zero reference: shared returns plain RMSE 0.5 (old gemv/fairness copies divided by zero)");

    std::printf("P1d scripted clock: exact median, min, max and repetition count\n");
    auto shared = [](auto&& run, bench::RepRule r) { return bench::time_ms<FakeClock>(run, r); };
    auto bad = [](auto&& run, bench::RepRule r) { return bad_median_time_ms<FakeClock>(run, r); };
    check(scripted(shared, {1000, 5, 1, 9, 3, 7}, {5, 5, 0.0}, 5, 1, 9, 5), "odd count: median 5, min 1, max 9, 5 reps");
    check(scripted(shared, {1000, 4, 2, 8, 6}, {4, 4, 0.0}, 6, 2, 8, 4), "even count: upper median 6 (samples[n/2]), 4 reps");
    check(scripted(shared, {1000, 4, 4, 4, 4, 4, 4, 4}, {3, 50, 20.0}, 4, 4, 4, 5), "time rule: stops at 5 reps once 20 ms accumulated");
    check(!scripted(bad, {1000, 5, 1, 9, 3, 7}, {5, 5, 0.0}, 5, 1, 9, 5), "[control] median taken as samples[0] fails the test");

    std::printf("P1 failures: %d\n", failures);
    return failures;
}
