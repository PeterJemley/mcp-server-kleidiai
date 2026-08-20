"""Smoke tests for corpus loading + retrieval against the committed corpus.

These double as the M1 retrieval smoke set: each asserts the top-ranked doc for
a representative query, so a corpus/retrieval regression fails loudly.
"""

from __future__ import annotations

import pytest

from mcp_server_kleidiai.corpus import load_chunks, search

# Known residual weaknesses of the two-level BM25 retriever (2026-08-05,
# post-swap — see evals/reports/report.md). strict=True so these fail loudly —
# and demand un-marking — when a future retriever fixes them.
_SIBLING_DOC_CONFUSION = pytest.mark.xfail(
    reason="D1/D2 residual: enablement queries pulled to sibling llama.cpp docs",
    strict=True,
)
_README_DILUTION = pytest.mark.xfail(
    reason="B residual: doc-level BM25 dilutes the README's dedicated "
    "'What is a micro-kernel?' section across the whole doc",
    strict=True,
)

SEEDED_IDS = {
    "kleidiai-readme",
    "llamacpp-build",
    "kleidiai-matmul-pack",
    "kleidiai-microkernel-names",
}


def test_corpus_loads_seeded_docs():
    ids = {c.doc_id for c in load_chunks()}
    assert SEEDED_IDS <= ids


@_SIBLING_DOC_CONFUSION
def test_enable_query_ranks_llamacpp_build_first():
    results = search("how do I enable KleidiAI when building llama.cpp", load_chunks())
    assert results and results[0].doc_id == "llamacpp-build"


@_README_DILUTION
def test_micro_kernel_query_ranks_readme_first():
    results = search("what is a micro-kernel ukernel in KleidiAI", load_chunks())
    assert results and results[0].doc_id == "kleidiai-readme"


def test_packing_query_ranks_matmul_pack_first():
    results = search("pack RHS weights and bias into blocks", load_chunks())
    assert results and results[0].doc_id == "kleidiai-matmul-pack"


def test_sme_identifier_query_ranks_names_doc_first():
    results = search("what does the sme tech identifier mean in a kernel name", load_chunks())
    assert results and results[0].doc_id == "kleidiai-microkernel-names"


def test_quantization_axis_query_ranks_names_doc_first():
    results = search("per-channel versus per-dimension quantization axis", load_chunks())
    assert results and results[0].doc_id == "kleidiai-microkernel-names"


def test_quant_scheme_query_ranks_names_doc_first():
    results = search("what quantization schemes does the naming grammar use", load_chunks())
    assert results and results[0].doc_id == "kleidiai-microkernel-names"


def test_sme_env_var_query_ranks_build_doc_first():
    results = search("which env var controls SME behavior in llama.cpp", load_chunks())
    assert results and results[0].doc_id == "llamacpp-build"


def test_empty_query_returns_nothing():
    assert search("", load_chunks()) == []


def test_results_carry_provenance():
    top = search("enable KleidiAI llama.cpp build", load_chunks())[0]
    assert top.url.startswith("https://")
    assert top.snippet
