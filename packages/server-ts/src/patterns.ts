/**
 * Curated pattern catalog + kernel-port planning — a faithful port of
 * packages/server-py/src/mcp_server_kleidiai/patterns.py. The catalog file
 * (patterns.yaml) is single-sourced from the Python package so the two
 * servers can never drift on content; response strings mirror the Python
 * implementation verbatim because the cross-SDK parity check diffs them.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parse } from "yaml";

import { findCorpusDir, loadManifest } from "./corpus.js";

/** One curated pattern as authored in patterns.yaml (sources are manifest doc ids). */
export interface Pattern {
  id: string;
  title: string;
  when_to_use: string;
  steps: string[];
  caveats?: string[];
  sources: string[];
}

function patternsPath(): string {
  const env = process.env.KLEIDIAI_PATTERNS_FILE;
  if (env) return env;
  // The repo root is wherever corpus/ lives; the canonical catalog ships
  // inside the Python package. In the published npm package, the prepack
  // step stages a copy at the package root instead.
  const root = dirname(findCorpusDir());
  const candidates = [
    join(root, "packages", "server-py", "src", "mcp_server_kleidiai", "patterns.yaml"),
    join(root, "patterns.yaml"),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  throw new Error("Could not locate patterns.yaml; set KLEIDIAI_PATTERNS_FILE");
}

let patterns: Pattern[] | null = null;
let docUrls: Map<string, string> | null = null;

/** Load (once) the curated pattern list from the canonical patterns.yaml. */
export function loadPatterns(): Pattern[] {
  if (patterns === null) {
    const data = parse(readFileSync(patternsPath(), "utf8"));
    patterns = data.patterns as Pattern[];
  }
  return patterns;
}

function urlsByDocId(): Map<string, string> {
  if (docUrls === null) {
    docUrls = new Map();
    for (const s of loadManifest(findCorpusDir())) docUrls.set(s.id, s.url ?? "");
  }
  return docUrls;
}

function cited(docIds: string[]): Array<{ doc_id: string; url: string }> {
  const urls = urlsByDocId();
  return docIds.map((d) => ({ doc_id: d, url: urls.get(d) ?? "" }));
}

function catalog(): Array<{ id: string; title: string; when_to_use: string }> {
  return loadPatterns().map((p) => ({
    id: p.id,
    title: p.title,
    when_to_use: p.when_to_use,
  }));
}

/** Look up a pattern by id; with no or an unknown id, return the catalog. */
export function getPattern(patternId = ""): Record<string, unknown> {
  for (const p of loadPatterns()) {
    if (p.id === patternId) {
      return {
        id: p.id,
        title: p.title,
        when_to_use: p.when_to_use,
        steps: p.steps,
        caveats: p.caveats ?? [],
        sources: cited(p.sources),
      };
    }
  }
  const note = patternId ? `unknown pattern id: '${patternId}'` : "no pattern id given";
  return { note: `${note}; available patterns listed`, available: catalog() };
}

const INT4_PER_CHANNEL = new Set(["int4-per-channel", "qsi4cx", "int4"]);
const INT4_PER_BLOCK = new Set(["int4-per-block", "qsi4c32", "q4_0"]);

/** Plan a matmul port to KleidiAI for the given quantization and CPU. */
export function planPort(
  rhsQuant: string,
  cpuFeatures: string[],
  rhsLayout = "nxk",
): Record<string, unknown> {
  const quant = rhsQuant.trim().toLowerCase();
  const features = new Set(cpuFeatures.map((f) => f.trim().toLowerCase()));
  const layout = rhsLayout.trim().toLowerCase();

  if (INT4_PER_CHANNEL.has(quant) && features.has("i8mm")) {
    const rhsPack =
      layout === "kxn"
        ? "kai_rhs_pack_kxn_qsi4cxp_qs4cxs1s0"
        : "kai_rhs_pack_nxk_qsi4cxp_qs4cxs1s0";
    return {
      supported: true,
      kernels: {
        rhs_pack: rhsPack,
        lhs_quant_pack: "kai_lhs_quant_pack_qai8dxp_f32",
        matmul: "kai_matmul_clamp_f32_qai8dxp4x8_qsi4cxp8x8_8x8x32_neon_i8mm",
      },
      call_order: [
        "RHS pack once at load (weights are static; params lhs_zero_point=1, rhs_zero_point=8)",
        "LHS quant+pack before every matmul (activations change)",
        "matmul over the packed buffers with clamp min/max",
      ],
      packing_args:
        "mr/nr/kr/sr and buffer sizes from the matmul kernel's kai_get_* helpers",
      build_flags: "-march=armv8.2-a+dotprod+i8mm",
      constraints: [
        "requires FEAT_I8MM",
        "k must be a multiple of 8 (LHS pack) and even (RHS pack)",
        "RHS native format: two int4 per byte, n * (k/2) bytes",
      ],
      sources: cited([
        "kleidiai-matmul-qsi4cx",
        "kleidiai-matmul-pack",
        "kleidiai-microkernel-names",
      ]),
    };
  }

  const llamaFeatures = ["sme", "sme2", "i8mm", "dotprod"];
  if (INT4_PER_BLOCK.has(quant) && llamaFeatures.some((f) => features.has(f))) {
    return {
      supported: true,
      recommendation:
        "The corpus documents this path through llama.cpp's KleidiAI " +
        "integration (GGML_CPU_KLEIDIAI=ON), not direct micro-kernel " +
        "calls: llama.cpp repacks Q4_0 weights once at load and picks " +
        "kernels by runtime priority SME2 -> I8MM -> DotProd.",
      pattern: "llamacpp-kleidiai-kernel-selection",
      sources: cited(["learnarm-llamacpp-sme2-integration", "llamacpp-build"]),
    };
  }

  const sorted = [...features].sort();
  return {
    supported: false,
    note:
      `The corpus does not document a direct port path for ` +
      `rhs_quant='${rhsQuant}' with cpu_features=[${sorted.map((f) => `'${f}'`).join(", ")}]. ` +
      "Documented paths: int4-per-channel on i8mm (direct calls), " +
      "int4-per-block via llama.cpp. Use search_kleidiai_docs to check " +
      "coverage rather than guessing kernel names.",
    sources: [],
  };
}
