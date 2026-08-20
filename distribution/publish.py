"""Cross-SDK publish entry point.

Publishes the Python package to PyPI, the TypeScript package to npm (v1.1+),
and submits/updates the registry entry on registry.modelcontextprotocol.io
via the mcp-publisher CLI.

Stub — real implementation lands in M4. See v0-decisions.md.
"""

from __future__ import annotations


def main() -> None:
    """Placeholder entry point; the manual flow lives in the /release
    checklist until this solidifies (keep the two in sync when automating)."""
    raise NotImplementedError("Publish flow lands in M4. See v0-decisions.md.")


if __name__ == "__main__":
    main()
