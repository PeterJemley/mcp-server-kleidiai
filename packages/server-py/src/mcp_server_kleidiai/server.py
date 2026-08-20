"""MCP server exposing the KleidiAI corpus as agent-callable tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from .corpus import DocChunk, load_chunks, search
from .patterns import get_pattern, plan_port

mcp = MCPServer("mcp-server-kleidiai")

_chunks: list[DocChunk] | None = None


def _corpus() -> list[DocChunk]:
    global _chunks
    if _chunks is None:
        _chunks = load_chunks()
    return _chunks


@mcp.tool()
def search_kleidiai_docs(query: str, limit: int = 5) -> list[dict[str, str | float]]:
    """Search the curated KleidiAI + llama.cpp Arm-optimization corpus.

    Returns passages ranked by relevance to the query. Each result carries its
    source doc id and URL so answers cite real Arm/llama.cpp docs rather than
    fabricating. Use for questions about enabling/using KleidiAI, its
    micro-kernels, and llama.cpp Arm builds.
    """
    return [
        {
            "doc_id": r.doc_id,
            "url": r.url,
            "heading": r.heading,
            "snippet": r.snippet,
            "score": r.score,
        }
        for r in search(query, _corpus(), limit=limit)
    ]


@mcp.tool()
def get_kleidiai_pattern(pattern_id: str = "") -> dict[str, Any]:
    """Fetch a curated KleidiAI workflow pattern by id.

    Patterns are provenance-cited recipes condensed from the corpus (e.g.
    enabling KleidiAI in llama.cpp, the int4 matmul micro-kernel set,
    decoding a kernel filename). Call with no pattern_id to list what's
    available. Prefer this over search when the task matches a pattern;
    every pattern cites the source docs to read for detail.
    """
    return get_pattern(pattern_id)


@mcp.tool()
def plan_kernel_port(rhs_quant: str, cpu_features: list[str], rhs_layout: str = "nxk") -> dict[str, Any]:
    """Plan a matmul port to KleidiAI micro-kernels.

    Given the weight quantization (e.g. "int4-per-channel"), the target
    CPU's features (e.g. ["dotprod", "i8mm"]), and the RHS layout ("nxk" or
    "kxn"), returns the exact micro-kernel set, call order, packing-argument
    source, build flags, and constraints — citing the corpus docs it comes
    from. Only plans paths the corpus documents; anything else returns
    supported=false with guidance instead of invented kernel names.
    """
    return plan_port(rhs_quant, cpu_features, rhs_layout)
