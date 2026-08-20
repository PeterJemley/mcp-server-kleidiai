"""Provenance checks for the committed corpus.

Corpus quality is the moat: every doc must trace to a real source (url,
commit, fetch date, SHA-256, license) recorded in corpus/manifest.yaml, and
nothing may live under corpus/ undocumented. A SHA-256 mismatch means a doc
was edited in-tree after fetch — exactly the fabrication these checks exist
to catch.
"""

from __future__ import annotations

import hashlib

import yaml

from mcp_server_kleidiai.corpus import find_corpus_dir

REQUIRED_FIELDS = ("id", "url", "commit", "fetched_at", "sha256", "path", "license")


def _manifest_sources() -> list[dict]:
    corpus_dir = find_corpus_dir()
    data = yaml.safe_load((corpus_dir / "manifest.yaml").read_text())
    return data["sources"]


def test_every_source_has_full_provenance():
    for src in _manifest_sources():
        missing = [f for f in REQUIRED_FIELDS if not src.get(f)]
        assert not missing, f"{src.get('id', src)}: missing provenance fields {missing}"


def test_committed_files_match_manifest_sha256():
    corpus_dir = find_corpus_dir()
    for src in _manifest_sources():
        if src.get("removed_at"):
            continue
        path = corpus_dir / src["path"]
        assert path.exists(), f"{src['id']}: {src['path']} listed but not committed"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == src["sha256"], f"{src['id']}: committed file differs from fetched content"


def test_no_undocumented_files_under_corpus():
    corpus_dir = find_corpus_dir()
    listed = {src["path"] for src in _manifest_sources()}
    on_disk = {
        str(p.relative_to(corpus_dir))
        for p in corpus_dir.rglob("*")
        if p.is_file() and not p.name.startswith(".") and p.name != "manifest.yaml"
    }
    undocumented = on_disk - listed
    assert not undocumented, f"files under corpus/ with no manifest entry: {sorted(undocumented)}"
