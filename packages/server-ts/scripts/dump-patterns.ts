/**
 * Dump pattern + planner outputs — TS side of the cross-SDK content-parity
 * check (see distribution/schema-sync/dump_patterns.py).
 */

import { getPattern, loadPatterns, planPort } from "../src/patterns.js";

function sortedJson(value: unknown): string {
  const keys = new Set<string>();
  JSON.stringify(value, (k, v) => {
    keys.add(k);
    return v;
  });
  return JSON.stringify(value, [...keys].sort(), 2);
}

const out = {
  catalog: getPattern(""),
  patterns: Object.fromEntries(loadPatterns().map((p) => [p.id, getPattern(p.id)])),
  plan_int4_i8mm: planPort("int4-per-channel", ["dotprod", "i8mm"]),
  plan_int4_kxn: planPort("qsi4cx", ["i8mm"], "kxn"),
  plan_q4_0_sme2: planPort("q4_0", ["sme2"]),
  plan_unsupported_flag: (planPort("int2-per-tensor", ["neon"]) as { supported: boolean })
    .supported,
};
console.log(sortedJson(out));
