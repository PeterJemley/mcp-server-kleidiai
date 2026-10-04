"""Measurements for config-seam.md: P1, P2, P3 and the must-fail controls.

Two files are read from git as they were at the preregistration commit: the
pre-seam corpus.py (P2 compares against exactly the retriever the plan
describes) and ab_dilution.py, the copy P1 compares against, deleted once the
seam reproduced it. P3 measures the seam commit itself, so later edits can't
change the recorded size.

Run: ../packages/server-py/.venv/bin/python retrieval/config-seam-check.py  (from evals/)
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import replace

import yaml

ARCHIVE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PREREG_COMMIT = "43dddc7"
SEAM_COMMIT = "ea01c59"
sys.path.insert(0, f"{ARCHIVE}/evals/retrieval")
import ab_configs as seam  # noqa: E402
from mcp_server_kleidiai import corpus as new  # noqa: E402


def git_show(commit, path):
    return subprocess.run(["git", "-C", ARCHIVE, "show", f"{commit}:{path}"],
                          capture_output=True, text=True, check=True).stdout


def from_git(commit, path, name):
    """Import a file as a module, as it was at a commit."""
    file = os.path.join(tempfile.mkdtemp(), f"{name}.py")
    with open(file, "w") as fh:
        fh.write(git_show(commit, path))
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


copy = from_git(PREREG_COMMIT, "evals/retrieval/ab_dilution.py", "ab_dilution")
old = from_git(PREREG_COMMIT, "packages/server-py/src/mcp_server_kleidiai/corpus.py", "corpus_committed")

qs = yaml.safe_load(open(f"{ARCHIVE}/evals/questions.yaml"))["questions"]
chunks = new.load_chunks()
print(f"module under test: {os.path.relpath(new.__file__, ARCHIVE)} (vs pre-seam corpus.py at {PREREG_COMMIT})\n"
      f"questions: {len(qs)}, chunks: {len(chunks)}\n")

# Index for the copy is built per stopword list, exactly as ab_dilution.main does.
copy_index = {stop: copy.build(chunks, stop) for stop in (copy.STOPWORDS_CURRENT, copy.STOPWORDS_NLTK)}


def copy_top1(question, stop, idf, rescue):
    return copy.top1(question, chunks, copy_index[stop], stop, idf, rescue)


def p1_compare(seam_cfg, stop, idf, rescue):
    return [(q["id"], seam.top1(q["question"], chunks, seam_cfg), copy_top1(q["question"], stop, idf, rescue)) for q in qs]


# --- P1: 8 configurations x 51 questions -------------------------------------
print("P1 equivalence (seam vs ab_dilution copy):")
total = agree = 0
mismatches = []
stops = {"cur-stop": copy.STOPWORDS_CURRENT, "nltk-stop": copy.STOPWORDS_NLTK}
for label, cfg in seam.CONFIGS.items():
    m = re.match(r"(\S+) idfcov=(\d) rescue=(\d)", label)
    stop, idf, rescue = stops[m.group(1)], m.group(2) == "1", m.group(3) == "1"
    assert cfg.stopwords == stop and cfg.idf_coverage == idf and cfg.section_rescue == rescue
    rows = p1_compare(cfg, stop, idf, rescue)
    ok = sum(a == b for _, a, b in rows)
    total += len(rows); agree += ok
    mismatches += [(label, *r) for r in rows if r[1] != r[2]]
    print(f"  {label:38s} {ok}/{len(rows)}")
print(f"  P1 TOTAL: {agree}/{total}")
for mm in mismatches:
    print("  MISMATCH", mm)

# --- P1 must-fail controls --------------------------------------------------
print("\nP1 controls (must report mismatches):")
for idf in (False, True):
    for rescue in (False, True):
        cfg = seam.CONFIGS[f"nltk-stop idfcov={int(idf)} rescue={int(rescue)}"]
        rows = p1_compare(cfg, copy.STOPWORDS_CURRENT, idf, rescue)
        print(f"  seam nltk vs copy cur-stop idf={int(idf)} rescue={int(rescue)}: {sum(a != b for _, a, b in rows)} mismatches")
for stopname, stop in stops.items():
    for rescue in (False, True):
        broken = replace(seam.CONFIGS[f"{stopname} idfcov=1 rescue={int(rescue)}"], idf_coverage=False)
        rows = p1_compare(broken, stop, True, rescue)
        print(f"  broken seam (ignores idf_coverage) vs copy {stopname} idf=1 rescue={int(rescue)}: {sum(a != b for _, a, b in rows)} mismatches")

# --- P2: default output unchanged -------------------------------------------
test_src = open(f"{ARCHIVE}/packages/server-py/tests/test_retrieval.py").read()
test_queries = re.findall(r'search\("([^"]*)"', test_src)
queries = [q["question"] for q in qs] + test_queries


def full(mod, query, **kw):
    return [(r.doc_id, r.url, r.heading, r.snippet, r.score) for r in mod.search(query, chunks, **kw)]


from pathlib import Path
old_chunks = old.load_chunks(Path(ARCHIVE) / "corpus")


def full_old(query):
    return [(r.doc_id, r.url, r.heading, r.snippet, r.score) for r in old.search(query, old_chunks)]


diffs = [q for q in queries if full(new, q) != full_old(q)]
print(f"\nP2 default output unchanged: {len(queries) - len(diffs)}/{len(queries)} queries identical "
      f"({len(qs)} QA + {len(test_queries)} test queries; full result lists)")
for q in diffs:
    print("  DIFF", q)
k12 = sum(full(new, q, config=replace(new.DEFAULT_CONFIG, k1=1.2)) != full_old(q) for q in queries)
print(f"P2 control (must report differences): k1=1.2 vs committed differs on {k12}/{len(queries)} queries")

# --- P3: size ---------------------------------------------------------------
numstat = subprocess.run(["git", "-C", ARCHIVE, "diff", "--numstat", PREREG_COMMIT, SEAM_COMMIT, "--",
                          "packages/server-py/src/mcp_server_kleidiai/corpus.py"], capture_output=True, text=True).stdout.split()
added, removed = int(numstat[0]), int(numstat[1])
driver = git_show(SEAM_COMMIT, "evals/retrieval/ab_configs.py")
driver_lines = driver.count("\n")
copy_lines = git_show(PREREG_COMMIT, "evals/retrieval/ab_dilution.py").count("\n")
print(f"\nP3 size: corpus.py +{added} -{removed} = net {added - removed}; ab_configs.py {driver_lines} lines; "
      f"total {added - removed + driver_lines} vs copy {copy_lines} (must be < {copy_lines})")
scoring = [pat for pat in ("math.", "findall(", "+ 1.0)") if pat in driver]
print(f"P3 scoring code in driver: {scoring if scoring else 'none'}")
