"""Entry point: run the MCP server over stdio."""

from __future__ import annotations

from .server import mcp


def main() -> None:
    """Serve the MCP tools over stdio (also the console-script entry point)."""
    mcp.run()


if __name__ == "__main__":
    main()
