/**
 * Dump the TS server's tool contract, normalized identically to the Python
 * dump (distribution/schema-sync/dump_contract.py). Uses a real in-memory
 * MCP client so the schema is what a client actually sees, not what we
 * think we registered.
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import { server } from "../src/server.js";

interface Prop {
  type?: string;
  default?: unknown;
  items?: { type?: string };
}

function normalize(inputSchema: {
  properties?: Record<string, Prop>;
  required?: string[];
}): Record<string, unknown> {
  const required = new Set(inputSchema.required ?? []);
  const params: Record<string, unknown> = {};
  for (const [name, prop] of Object.entries(inputSchema.properties ?? {})) {
    const entry: Record<string, unknown> = {
      type: prop.type,
      required: required.has(name),
    };
    if ("default" in prop) entry.default = prop.default;
    if (prop.type === "array") entry.items = prop.items?.type;
    params[name] = entry;
  }
  return params;
}

function sortedJson(value: unknown): string {
  const keys = new Set<string>();
  JSON.stringify(value, (k, v) => {
    keys.add(k);
    return v;
  });
  return JSON.stringify(value, [...keys].sort(), 2);
}

const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
const client = new Client({ name: "contract-dump", version: "0.0.1" });
await server.connect(serverTransport);
await client.connect(clientTransport);

const { tools } = await client.listTools();
const contract: Record<string, unknown> = {};
for (const t of tools) {
  contract[t.name] = normalize(t.inputSchema as never);
}
console.log(sortedJson(contract));
await client.close();
