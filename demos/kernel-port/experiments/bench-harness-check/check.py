"""Measurements for bench-harness.md: P1-P4 and the must-fail controls.

The old programs are read from git as they were at the preregistration commit,
so the comparison is against exactly the copies the plan describes. Everything
runs on x86-64 Linux: stand-ins/ replaces the Arm-only pieces (KleidiAI's
kernels, Accelerate, arm_neon.h) with plain float code, so outputs carry real
error but timings mean nothing and are masked.

Run from demos/kernel-port, on a clean tree, after ./fetch_kleidiai.sh:
    python3 experiments/bench-harness-check/check.py
It prints its results and, once P4 has used the clean tree, writes them to
check.out beside this file. Exit code = number of failed checks.
"""
import io
import os
import platform
import shutil
import subprocess
import sys
import tempfile

PREREG_COMMIT = "e74a3ac"
HERE = os.path.dirname(os.path.abspath(__file__))
KP = os.path.abspath(os.path.join(HERE, "..", ".."))
STANDINS = os.path.join(HERE, "stand-ins")
WORK = os.path.join(KP, "build", "bench-harness-check")
KAI = os.path.join(KP, "third_party", "kleidiai")
CXX = os.environ.get("CXX", "g++")
FLAGS = ["-O3", "-ffast-math", "-std=c++17", "-march=native"]
PROGRAMS = {"main": "src/main.cpp", "gemv": "experiments/gemv-decode.cpp",
            "fairness": "experiments/baseline-fairness.cpp"}

if platform.machine() != "x86_64":
    sys.exit("x86-64 only: the stand-ins replace code that exists only on Arm")
if not os.path.isdir(KAI):
    sys.exit("run ./fetch_kleidiai.sh first")
os.chdir(KP)


class Tee(io.StringIO):
    def write(self, s):
        sys.__stdout__.write(s)
        return super().write(s)


sys.stdout = Tee()
shutil.rmtree(WORK, ignore_errors=True)
failures = 0


def sh(*args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw).stdout


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    return path


def template(demo_reset):
    """The baseline main.cpp that demo-reset.sh writes into the workspace."""
    start = demo_reset.index("\n", demo_reset.index("cat > \"$dest/src/main.cpp\" <<'CPP'\n")) + 1
    return demo_reset[start:demo_reset.index("\nCPP\n", start) + 1]


def extract(text, start):
    """From `start` through its matching closing brace, verbatim."""
    i = text.index(start)
    depth = 0
    for k in range(text.index("{", i), len(text)):
        depth += (text[k] == "{") - (text[k] == "}")
        if depth == 0:
            return text[i:k + 1]


# --- Sources: old from git, new from the working tree -----------------------
old = {name: sh("git", "show", f"{PREREG_COMMIT}:./{path}") for name, path in PROGRAMS.items()}
old["template"] = template(sh("git", "show", f"{PREREG_COMMIT}:./demo-reset.sh"))
new = {name: open(path).read() for name, path in PROGRAMS.items()}
new["template"] = template(open("demo-reset.sh").read())
header = open("src/bench_harness.h").read()
broken = header.replace("std::sqrt(err / mag) :", "(err / mag) :")
assert broken != header

src = {}
for version, texts in (("old", old), ("new", new)):
    for name, text in texts.items():
        src[f"{name}-{version}"] = write(f"{WORK}/{version}/{name}.cpp", text)
src["main-broken"] = write(f"{WORK}/broken/main.cpp", new["main"])
write(f"{WORK}/broken/bench_harness.h", broken)

o = old
gemv_reps = next(line.strip() for line in o["gemv"].splitlines() if "const size_t reps = " in line)
write(f"{WORK}/old_extracted.h", "\n".join([
    f"// Extracted verbatim from demos/kernel-port at {PREREG_COMMIT} (bench-harness.md P1).",
    "#pragma once", "#include <algorithm>", "#include <chrono>", "#include <cmath>", "#include <cstddef>",
    "#include <vector>",
    "namespace old_main {", extract(o["main"], "template <typename Run>\ndouble median_ms(double gflop"),
    extract(o["main"], "double rel_rmse("), "}",
    "namespace old_tmpl {", extract(o["template"], "template <typename Run>\ndouble median_ms(double gflop"),
    extract(o["template"], "double rel_rmse("), "}",
    "namespace old_gemv {", extract(o["gemv"], "template <typename Run>\ndouble median_ms(size_t reps"),
    extract(o["gemv"], "double rel_rmse("),
    f"inline size_t reps_for(double gflop) {{ {gemv_reps} return reps; }}", "}",
    "namespace old_fair {", extract(o["fairness"], "struct Timing {") + ";",
    extract(o["fairness"], "template <typename Run>\nTiming time_ms("),
    extract(o["fairness"], "double rel_rmse("), "}", ""]))

# --- Build -------------------------------------------------------------------
kai_inc = ["-I", KAI, "-I", f"{KAI}/kai/ukernels/matmul/pack",
           "-I", f"{KAI}/kai/ukernels/matmul/matmul_clamp_f32_qai8dxp_qsi4cxp"]
extra = {"main": [f"{STANDINS}/int4_stub.cpp"], "template": [],
         "gemv": kai_inc + ["-I", STANDINS, f"{STANDINS}/kai_stub.cpp"],
         "fairness": ["-I", STANDINS, f"{STANDINS}/int4_stub.cpp"]}
for binary, path in src.items():
    sh(CXX, *FLAGS, "-I", "src", path, "src/matmul_f32.cpp", *extra[binary.split("-")[0]], "-o", f"{WORK}/{binary}")
sh(CXX, "-O2", "-std=c++17", "-I", "src", "-I", WORK, f"{HERE}/p1.cpp", "-o", f"{WORK}/p1")
print(f"built {len(src)} programs (old at {PREREG_COMMIT}, new, and the no-sqrt control) and the P1 test\n")

# --- P1: protocol --------------------------------------------------------------
p1 = subprocess.run([f"{WORK}/p1"], capture_output=True, text=True)
print(p1.stdout)
failures += p1.returncode

# --- P2: behaviour, timing columns masked -----------------------------------
KEEP = {"main": ("shape", "impl", "weights MB", "rel RMSE"),
        "template": ("shape", "impl", "weights MB", "rel RMSE"),
        "gemv": ("M", "variant", "kind", "rel RMSE"),
        "fairness": ("part", "M", "N", "K", "impl", "weights MB", "rel RMSE", "check")}
out = {}
for binary in src:
    # baseline-fairness refuses to run unless Accelerate is pinned to one thread.
    run = subprocess.run([f"{WORK}/{binary}"], capture_output=True, text=True, check=True,
                         env={**os.environ, "VECLIB_MAXIMUM_THREADS": "1"})
    out[binary] = write(f"{WORK}/out/{binary}.md", run.stdout)


def masked(binary):
    lines = open(out[binary]).read().splitlines()
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in lines if line.startswith("|")]
    keep = [rows[0].index(k) for k in KEEP[binary.split("-")[0]]]
    other = [line for line in lines if not line.startswith("|")]
    return [tuple(r[i] for i in keep) for r in rows[2:]] + other, [h for i, h in enumerate(rows[0]) if i not in keep]


print("P2 behaviour: old vs new output, timing columns masked")
for name, keep in KEEP.items():
    (a, hidden), (b, _) = masked(f"{name}-old"), masked(f"{name}-new")
    failures += a != b
    print(f"  {'ok' if a == b else 'FAIL':4s} {name:9s} {len(a)} lines old, {len(b)} new; "
          f"compared {', '.join(keep)} and any text outside the table; masked {', '.join(hidden)}")
    for x, y in zip(a, b):
        if x != y:
            print(f"       old {x}\n       new {y}")
(a, _), (b, _) = masked("main-broken"), masked("main-new")
diff = sum(x != y for x, y in zip(a, b))
failures += diff == 0
print(f"  {'ok' if diff else 'FAIL':4s} [control] rel_rmse without sqrt changes {diff}/{len(b)} masked lines of main.cpp (must differ)")

# --- P3: one copy ------------------------------------------------------------
# This checker names the strings it counts, so it excludes itself.
SKIP = (":!*.md", ":!experiments/bench-harness-check")


def files_with(pattern, commit=None):
    """Files containing pattern at commit, or in the working tree (untracked files included)."""
    where = [commit] if commit else []
    grep = subprocess.run(["git", "grep", *([] if commit else ["--untracked"]), "-l", "-F", pattern, *where,
                           "--", ".", *SKIP], capture_output=True, text=True)
    assert grep.returncode in (0, 1), grep.stderr  # 1 means no file matches
    return [f.split(":", 1)[1] if commit else f for f in grep.stdout.split()]


print("\nP3 one copy: files under demos/kernel-port containing each string (Markdown and this checker excluded)")
for pattern, prereg in (("steady_clock::now", True), ("::now()", False), ("double rel_rmse(", True)):
    before, after = files_with(pattern, PREREG_COMMIT), files_with(pattern)
    ok = after == ["src/bench_harness.h"]
    failures += prereg and not ok
    label = "preregistered" if prereg else "not preregistered: widened after the result, see the deviation log"
    print(f"  {'ok' if ok else 'FAIL':4s} {pattern!r} ({label}): before {len(before)} {before}; after {len(after)} {after}")

# --- P4: the recording workspace ---------------------------------------------
print("\nP4 workspace")
ws = os.path.join(tempfile.mkdtemp(), "ws")  # demo-reset.sh refuses a workspace inside the repo
reset = subprocess.run(["./demo-reset.sh", "workspace", ws], capture_output=True, text=True)
files = sh("git", "-C", ws, "ls-files").split() if reset.returncode == 0 else []
compiled = reset.returncode == 0 and subprocess.run(
    [CXX, *FLAGS, f"{ws}/src/main.cpp", f"{ws}/src/matmul_f32.cpp", "-o", f"{WORK}/ws-bench"]).returncode == 0
for ok, what in ((reset.returncode == 0, f"demo-reset.sh workspace exits 0 (leak check passed): {reset.returncode}"),
                 ("src/bench_harness.h" in files, "workspace includes src/bench_harness.h"),
                 (compiled, "workspace baseline compiles")):
    failures += not ok
    print(f"  {'ok' if ok else 'FAIL':4s} {what}")
if reset.returncode:
    print(reset.stderr)
print(f"  workspace files: {' '.join(files)}")

print(f"\nfailed checks: {failures}")
with open(os.path.join(HERE, "check.out"), "w") as fh:
    fh.write(sys.stdout.getvalue())
sys.exit(failures)
