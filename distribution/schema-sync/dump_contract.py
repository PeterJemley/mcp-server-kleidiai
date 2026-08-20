"""Dump the Python server's tool contract, normalized for cross-SDK diffing.

The contract is what both servers must agree on: tool names, parameter
names, types (with array item types), required flags, and defaults.
Generator cosmetics (pydantic/zod titles, schema envelopes) are normalized
away — the claim is "identical tool surface", not "identical schema bytes".
Output is sorted-key JSON on stdout; diff against the TS dump.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp_server_kleidiai.server import mcp


def normalize(input_schema: dict[str, Any]) -> dict[str, Any]:
    """Reduce a JSON schema to the contract: per-param type/required/default
    (plus array item type), dropping generator cosmetics like titles."""
    required = set(input_schema.get("required", []))
    params: dict[str, Any] = {}
    for name, prop in input_schema.get("properties", {}).items():
        entry: dict[str, Any] = {"type": prop.get("type"), "required": name in required}
        if "default" in prop:
            entry["default"] = prop["default"]
        if prop.get("type") == "array":
            entry["items"] = prop.get("items", {}).get("type")
        params[name] = entry
    return params


async def main() -> None:
    """Print the normalized contract of every registered tool as sorted JSON."""
    tools = {t.name: normalize(t.input_schema) for t in await mcp.list_tools()}
    print(json.dumps(tools, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
