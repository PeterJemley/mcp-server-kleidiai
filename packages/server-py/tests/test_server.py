"""Tests for the MCP tool surface.

The tool schema is the cross-SDK contract (the TypeScript port must expose an
identical one), so it is asserted explicitly: adding or renaming a tool should
break here and be updated deliberately.
"""

from __future__ import annotations

import asyncio
import json

from mcp_server_kleidiai.server import mcp, search_kleidiai_docs

EXPECTED_TOOLS = {"search_kleidiai_docs", "get_kleidiai_pattern", "plan_kernel_port"}


def test_tool_surface_matches_contract():
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert set(tools) == EXPECTED_TOOLS

    schema = tools["search_kleidiai_docs"].input_schema
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["type"] == "string"
    assert schema["properties"]["limit"] == {"default": 5, "title": "Limit", "type": "integer"}

    schema = tools["get_kleidiai_pattern"].input_schema
    assert "required" not in schema or schema["required"] == []
    assert schema["properties"]["pattern_id"]["type"] == "string"

    schema = tools["plan_kernel_port"].input_schema
    assert set(schema["required"]) == {"rhs_quant", "cpu_features"}
    assert schema["properties"]["cpu_features"]["type"] == "array"
    assert schema["properties"]["rhs_layout"]["default"] == "nxk"


def test_call_tool_returns_cited_results():
    result = asyncio.run(
        mcp.call_tool("search_kleidiai_docs", {"query": "enable KleidiAI in a llama.cpp build"})
    )
    content = result.content
    assert content
    results = [json.loads(c.text) for c in content]
    for r in results:
        assert set(r) == {"doc_id", "url", "heading", "snippet", "score"}
        assert r["url"].startswith("https://")
        assert r["snippet"]


def test_limit_is_respected():
    assert len(search_kleidiai_docs("KleidiAI micro-kernel packing", limit=2)) <= 2


def test_empty_query_returns_no_results():
    assert search_kleidiai_docs("") == []
