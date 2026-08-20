"""Tests for the pattern catalog and the kernel-port planner.

Same integrity rules as the corpus: every pattern must cite manifest doc ids
that exist (its provenance), and the planner may only name kernels for paths
the corpus documents.
"""

from __future__ import annotations

from mcp_server_kleidiai.corpus import find_corpus_dir, load_manifest
from mcp_server_kleidiai.patterns import get_pattern, load_patterns, plan_port

KNOWN_PATTERN_IDS = {
    "enable-kleidiai-llamacpp",
    "int4-matmul-microkernel-set",
    "decode-microkernel-name",
    "llamacpp-kleidiai-kernel-selection",
}


def test_catalog_matches_expected_ids():
    assert {p["id"] for p in load_patterns()} == KNOWN_PATTERN_IDS


def test_every_pattern_cites_known_manifest_docs():
    manifest_ids = {s["id"] for s in load_manifest(find_corpus_dir())}
    for p in load_patterns():
        assert p["sources"], f"{p['id']}: a pattern without sources is fabrication"
        unknown = set(p["sources"]) - manifest_ids
        assert not unknown, f"{p['id']}: cites doc ids not in the manifest: {unknown}"


def test_get_pattern_resolves_provenance_urls():
    p = get_pattern("int4-matmul-microkernel-set")
    assert p["steps"]
    assert all(s["url"].startswith("https://") for s in p["sources"])


def test_get_pattern_without_id_returns_catalog():
    result = get_pattern()
    assert {e["id"] for e in result["available"]} == KNOWN_PATTERN_IDS


def test_get_pattern_unknown_id_returns_catalog_with_note():
    result = get_pattern("no-such-pattern")
    assert "no-such-pattern" in result["note"]
    assert result["available"]


def test_plan_port_int4_per_channel_on_i8mm():
    plan = plan_port("int4-per-channel", ["dotprod", "i8mm"])
    assert plan["supported"]
    assert plan["kernels"] == {
        "rhs_pack": "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0",
        "lhs_quant_pack": "kai_lhs_quant_pack_qai8dxp_f32",
        "matmul": "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm",
    }
    assert plan["sources"]


def test_plan_port_respects_kxn_layout():
    plan = plan_port("qsi4cx", ["i8mm"], rhs_layout="kxn")
    assert plan["kernels"]["rhs_pack"] == "kai_rhs_pack_kxn_qsi4cxp_qs4cxs1s0"


def test_plan_port_per_block_routes_to_llamacpp_path():
    plan = plan_port("q4_0", ["sme2"])
    assert plan["supported"]
    assert plan["pattern"] == "llamacpp-kleidiai-kernel-selection"


def test_plan_port_refuses_undocumented_paths():
    plan = plan_port("int2-per-tensor", ["neon"])
    assert not plan["supported"]
    assert "search_kleidiai_docs" in plan["note"]
