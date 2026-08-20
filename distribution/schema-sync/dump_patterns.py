"""Dump pattern + planner outputs — Python side of the cross-SDK content-
parity check. Covers the catalog, every pattern by id, and the planner's
documented paths (plus the supported flag on an undocumented one).
Sorted-key JSON on stdout; diff against the TS dump.
"""

from __future__ import annotations

import json

from mcp_server_kleidiai.patterns import get_pattern, load_patterns, plan_port


def main() -> None:
    """Print catalog, every pattern, and canonical planner outputs as JSON."""
    out = {
        "catalog": get_pattern(""),
        "patterns": {p["id"]: get_pattern(p["id"]) for p in load_patterns()},
        "plan_int4_i8mm": plan_port("int4-per-channel", ["dotprod", "i8mm"]),
        "plan_int4_kxn": plan_port("qsi4cx", ["i8mm"], "kxn"),
        "plan_q4_0_sme2": plan_port("q4_0", ["sme2"]),
        "plan_unsupported_flag": plan_port("int2-per-tensor", ["neon"])["supported"],
    }
    print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
