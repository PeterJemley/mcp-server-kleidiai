/** Pattern catalog + planner tests — the TS mirror of test_patterns.py. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { getPattern, loadPatterns, planPort } from "../src/patterns.js";

const KNOWN_IDS = new Set([
  "enable-kleidiai-llamacpp",
  "int4-matmul-microkernel-set",
  "decode-microkernel-name",
  "llamacpp-kleidiai-kernel-selection",
]);

test("catalog matches expected ids", () => {
  assert.deepEqual(new Set(loadPatterns().map((p) => p.id)), KNOWN_IDS);
});

test("get_pattern resolves provenance urls", () => {
  const p = getPattern("int4-matmul-microkernel-set") as {
    steps: string[];
    sources: Array<{ url: string }>;
  };
  assert.ok(p.steps.length > 0);
  for (const s of p.sources) assert.ok(s.url.startsWith("https://"));
});

test("get_pattern without id returns catalog", () => {
  const result = getPattern() as { available: Array<{ id: string }> };
  assert.deepEqual(new Set(result.available.map((e) => e.id)), KNOWN_IDS);
});

test("plan_port int4 per-channel on i8mm names the three kernels", () => {
  const plan = planPort("int4-per-channel", ["dotprod", "i8mm"]) as {
    supported: boolean;
    kernels: Record<string, string>;
  };
  assert.ok(plan.supported);
  assert.deepEqual(plan.kernels, {
    rhs_pack: "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0",
    lhs_quant_pack: "kai_lhs_quant_pack_qai8dxp_f32",
    matmul: "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm",
  });
});

test("plan_port refuses undocumented paths", () => {
  const plan = planPort("int2-per-tensor", ["neon"]) as { supported: boolean; note: string };
  assert.equal(plan.supported, false);
  assert.ok(plan.note.includes("search_kleidiai_docs"));
});
