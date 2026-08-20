/**
 * MCP server exposing the KleidiAI corpus as agent-callable tools — the
 * TypeScript sibling of packages/server-py. The tool surface (names,
 * parameters, types, defaults, descriptions' meaning) is the cross-SDK
 * contract; the parity checks in distribution/schema-sync fail CI if the
 * two servers drift.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { type DocChunk, loadChunks, search } from "./corpus.js";
import { getPattern, planPort } from "./patterns.js";

/** The MCP server instance; index.ts connects it to stdio, tests and parity
 * dumps connect it to in-memory transports. */
export const server = new McpServer({ name: "mcp-server-kleidiai", version: "0.0.1" });

let chunks: DocChunk[] | null = null;

function corpus(): DocChunk[] {
  if (chunks === null) chunks = loadChunks();
  return chunks;
}

function asText(value: unknown): { content: Array<{ type: "text"; text: string }> } {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }] };
}

server.registerTool(
  "search_kleidiai_docs",
  {
    description:
      "Search the curated KleidiAI + llama.cpp Arm-optimization corpus.\n\n" +
      "Returns passages ranked by relevance to the query. Each result carries its " +
      "source doc id and URL so answers cite real Arm/llama.cpp docs rather than " +
      "fabricating. Use for questions about enabling/using KleidiAI, its " +
      "micro-kernels, and llama.cpp Arm builds.",
    inputSchema: {
      query: z.string(),
      limit: z.number().int().default(5),
    },
  },
  async ({ query, limit }) => asText(search(query, corpus(), limit)),
);

server.registerTool(
  "get_kleidiai_pattern",
  {
    description:
      "Fetch a curated KleidiAI workflow pattern by id.\n\n" +
      "Patterns are provenance-cited recipes condensed from the corpus (e.g. " +
      "enabling KleidiAI in llama.cpp, the int4 matmul micro-kernel set, " +
      "decoding a kernel filename). Call with no pattern_id to list what's " +
      "available. Prefer this over search when the task matches a pattern; " +
      "every pattern cites the source docs to read for detail.",
    inputSchema: {
      pattern_id: z.string().default(""),
    },
  },
  async ({ pattern_id }) => asText(getPattern(pattern_id)),
);

server.registerTool(
  "plan_kernel_port",
  {
    description:
      "Plan a matmul port to KleidiAI micro-kernels.\n\n" +
      'Given the weight quantization (e.g. "int4-per-channel"), the target ' +
      'CPU\'s features (e.g. ["dotprod", "i8mm"]), and the RHS layout ("nxk" or ' +
      '"kxn"), returns the exact micro-kernel set, call order, packing-argument ' +
      "source, build flags, and constraints — citing the corpus docs it comes " +
      "from. Only plans paths the corpus documents; anything else returns " +
      "supported=false with guidance instead of invented kernel names.",
    inputSchema: {
      rhs_quant: z.string(),
      cpu_features: z.array(z.string()),
      rhs_layout: z.string().default("nxk"),
    },
  },
  async ({ rhs_quant, cpu_features, rhs_layout }) =>
    asText(planPort(rhs_quant, cpu_features, rhs_layout)),
);
