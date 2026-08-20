/**
 * Retrieval smoke tests — the TS mirror of the Python suite
 * (packages/server-py/tests/test_retrieval.py), including its two known
 * residual failures, asserted inverted (the TS equivalent of strict xfail):
 * if a retriever change fixes them, these assertions fail and demand
 * un-inverting in BOTH suites together.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { loadChunks, search } from "../src/corpus.js";

const chunks = loadChunks();

test("corpus loads seeded docs", () => {
  const ids = new Set(chunks.map((c) => c.docId));
  for (const id of [
    "kleidiai-readme",
    "llamacpp-build",
    "kleidiai-matmul-pack",
    "kleidiai-microkernel-names",
  ]) {
    assert.ok(ids.has(id), `missing ${id}`);
  }
});

test("KNOWN FAILURE (D1/D2 residual): enable query pulled to sibling doc", () => {
  const results = search("how do I enable KleidiAI when building llama.cpp", chunks);
  assert.notEqual(results[0]?.doc_id, "llamacpp-build");
});

test("KNOWN FAILURE (B residual): micro-kernel definition diluted in README", () => {
  const results = search("what is a micro-kernel ukernel in KleidiAI", chunks);
  assert.notEqual(results[0]?.doc_id, "kleidiai-readme");
});

test("packing query ranks matmul-pack first", () => {
  const results = search("pack RHS weights and bias into blocks", chunks);
  assert.equal(results[0]?.doc_id, "kleidiai-matmul-pack");
});

test("sme identifier query ranks names doc first", () => {
  const results = search("what does the sme tech identifier mean in a kernel name", chunks);
  assert.equal(results[0]?.doc_id, "kleidiai-microkernel-names");
});

test("quantization axis query ranks names doc first", () => {
  const results = search("per-channel versus per-dimension quantization axis", chunks);
  assert.equal(results[0]?.doc_id, "kleidiai-microkernel-names");
});

test("sme env var query ranks build doc first", () => {
  const results = search("which env var controls SME behavior in llama.cpp", chunks);
  assert.equal(results[0]?.doc_id, "llamacpp-build");
});

test("empty query returns nothing", () => {
  assert.deepEqual(search("", chunks), []);
});

test("results carry provenance", () => {
  const top = search("enable KleidiAI llama.cpp build", chunks)[0]!;
  assert.ok(top.url.startsWith("https://"));
  assert.ok(top.snippet.length > 0);
});
