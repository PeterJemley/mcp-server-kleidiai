"""Promptfoo custom provider: scores search_kleidiai_docs retrieval.

Given a question as the prompt, returns the top-1 doc id the server's retrieval
surfaces. Run under the server venv (PROMPTFOO_PYTHON) so mcp_server_kleidiai is
importable. Deterministic — no LLM, no API key.

The stdio MCP wiring itself is covered by the server's end-to-end smoke test;
this provider scores the retrieval that wiring serves.
"""

from __future__ import annotations

from mcp_server_kleidiai.corpus import load_chunks, search

_chunks = None


def _corpus():
    global _chunks
    if _chunks is None:
        _chunks = load_chunks()
    return _chunks


def call_api(prompt, options, context):
    """Promptfoo provider hook: the prompt is the question; output is the
    top-1 doc id (empty string when retrieval returns nothing)."""
    results = search(prompt, _corpus(), limit=5)
    top = results[0].doc_id if results else ""
    return {"output": top}
