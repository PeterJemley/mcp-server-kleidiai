"""Curated pattern catalog + kernel-port planning over the committed corpus.

Patterns are derived content (patterns.yaml, shipped with the package): each
condenses one workflow the corpus documents and cites the manifest doc ids it
comes from. Source URLs are resolved from corpus/manifest.yaml at serve time,
so a pattern citing an unknown doc id fails loudly in tests rather than
serving unattributed advice. The port planner is a deterministic mapping over
the same catalog's facts — it only plans what the corpus documents, and says
so when asked for anything else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .corpus import find_corpus_dir, load_manifest

_PATTERNS_PATH = Path(__file__).parent / "patterns.yaml"

_patterns: list[dict[str, Any]] | None = None
_doc_urls: dict[str, str] | None = None


def load_patterns() -> list[dict[str, Any]]:
    """Return the curated pattern list from the packaged patterns.yaml."""
    global _patterns
    if _patterns is None:
        data = yaml.safe_load(_PATTERNS_PATH.read_text())
        _patterns = list(data["patterns"])
    return _patterns


def _urls_by_doc_id() -> dict[str, str]:
    global _doc_urls
    if _doc_urls is None:
        _doc_urls = {s["id"]: s.get("url", "") for s in load_manifest(find_corpus_dir())}
    return _doc_urls


def _cited(doc_ids: list[str]) -> list[dict[str, str]]:
    urls = _urls_by_doc_id()
    return [{"doc_id": d, "url": urls.get(d, "")} for d in doc_ids]


def _catalog() -> list[dict[str, str]]:
    return [
        {"id": p["id"], "title": p["title"], "when_to_use": p["when_to_use"]}
        for p in load_patterns()
    ]


def get_pattern(pattern_id: str = "") -> dict[str, Any]:
    """Look up a pattern by id; with no or an unknown id, return the catalog."""
    for p in load_patterns():
        if p["id"] == pattern_id:
            return {
                "id": p["id"],
                "title": p["title"],
                "when_to_use": p["when_to_use"],
                "steps": p["steps"],
                "caveats": p.get("caveats", []),
                "sources": _cited(p["sources"]),
            }
    note = f"unknown pattern id: {pattern_id!r}" if pattern_id else "no pattern id given"
    return {"note": f"{note}; available patterns listed", "available": _catalog()}


# The corpus documents exactly one direct-call int4 port path (per-channel on
# i8mm, the qsi4cx guide) and one llama.cpp-integrated path (per-block via
# GGML). The planner maps onto those and refuses to invent others.
_INT4_PER_CHANNEL = {"int4-per-channel", "qsi4cx", "int4"}
_INT4_PER_BLOCK = {"int4-per-block", "qsi4c32", "q4_0"}


def plan_port(rhs_quant: str, cpu_features: list[str], rhs_layout: str = "nxk") -> dict[str, Any]:
    """Plan a matmul port to KleidiAI for the given quantization and CPU."""
    quant = rhs_quant.strip().lower()
    features = {f.strip().lower() for f in cpu_features}
    layout = rhs_layout.strip().lower()

    if quant in _INT4_PER_CHANNEL and "i8mm" in features:
        rhs_pack = (
            "kai_rhs_pack_kxn_qsi4cxp_qs4cxs1s0"
            if layout == "kxn"
            else "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0"
        )
        return {
            "supported": True,
            "kernels": {
                "rhs_pack": rhs_pack,
                "lhs_quant_pack": "kai_lhs_quant_pack_qai8dxp_f32",
                "matmul": "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm",
            },
            "call_order": [
                "RHS pack once at load (weights are static; params lhs_zero_point=1, rhs_zero_point=8)",
                "LHS quant+pack before every matmul (activations change)",
                "matmul over the packed buffers with clamp min/max",
            ],
            "packing_args": "mr/nr/kr/sr and buffer sizes from the matmul kernel's kai_get_* helpers",
            "build_flags": "-march=armv8.2-a+dotprod+i8mm",
            "constraints": [
                "requires FEAT_I8MM",
                "k must be a multiple of 8 (LHS pack) and even (RHS pack)",
                "RHS native format: two int4 per byte, n * (k/2) bytes",
            ],
            "sources": _cited(["kleidiai-matmul-qsi4cx", "kleidiai-matmul-pack", "kleidiai-microkernel-names"]),
        }

    if quant in _INT4_PER_BLOCK and features & {"sme", "sme2", "i8mm", "dotprod"}:
        return {
            "supported": True,
            "recommendation": (
                "The corpus documents this path through llama.cpp's KleidiAI "
                "integration (GGML_CPU_KLEIDIAI=ON), not direct micro-kernel "
                "calls: llama.cpp repacks Q4_0 weights once at load and picks "
                "kernels by runtime priority SME2 -> I8MM -> DotProd."
            ),
            "pattern": "llamacpp-kleidiai-kernel-selection",
            "sources": _cited(["learnarm-llamacpp-sme2-integration", "llamacpp-build"]),
        }

    return {
        "supported": False,
        "note": (
            f"The corpus does not document a direct port path for "
            f"rhs_quant={rhs_quant!r} with cpu_features={sorted(features)!r}. "
            "Documented paths: int4-per-channel on i8mm (direct calls), "
            "int4-per-block via llama.cpp. Use search_kleidiai_docs to check "
            "coverage rather than guessing kernel names."
        ),
        "sources": [],
    }
